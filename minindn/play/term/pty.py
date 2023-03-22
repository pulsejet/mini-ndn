import fcntl, struct, termios, os
import subprocess
import select
import msgpack
import pty

from io import BufferedWriter
from threading import Thread
from typing import Optional, TYPE_CHECKING

from minindn.play.term.cbuf import CircularByteBuffer
from minindn.play.consts import WSKeys, WSFunctions

if TYPE_CHECKING:
    from minindn.play.term.term import TermExecutor

class Pty:
    id: str
    name: str
    master: int
    stdin: BufferedWriter
    thread: Thread
    slave: int
    process: Optional[subprocess.Popen] = None
    buffer: CircularByteBuffer
    executor: 'TermExecutor'

    def __init__(self, executor):
        self.master, self.slave = pty.openpty()
        self.buffer = CircularByteBuffer(16000)
        self.executor = executor

    # Send output to UI thread
    def ui_out_pty_thread(self):
        poller = select.poll()
        poller.register(self.master, select.POLLIN)
        while not self.process or self.process.poll() is None:
            if res := poller.poll(5):
                # Check if poller is closed
                if res[0][1] == select.POLLHUP:
                    break

                # Find the number of bytes available to read
                bytes_available = fcntl.ioctl(self.master, termios.FIONREAD, struct.pack('I', 0))
                bytes_available = struct.unpack('I', bytes_available)[0]
                bytes_to_read = min(bytes_available, 4096)

                # This should never really happen
                if bytes_to_read == 0:
                    continue

                # Read everything available
                bytes = None
                try:
                    bytes = os.read(self.master, bytes_to_read)
                except OSError as e:
                    break

                # Send to UI
                self.executor._send_pty_out(bytes, self.id)
                self.buffer.write(bytes)

        self.executor.socket.send_all(msgpack.dumps({
            WSKeys.MSG_KEY_FUN: WSFunctions.CLOSE_TERMINAL,
            WSKeys.MSG_KEY_ID: self.id,
        }))

        os.close(self.master)
        os.close(self.slave)
        del self.executor.pty_list[self.id]

    def start(self):
        self.executor.pty_list[self.id] = self
        self.stdin = os.fdopen(self.master, 'wb')
        self.thread = Thread(target=self.ui_out_pty_thread, args=(), daemon=True)
        self.thread.start()
