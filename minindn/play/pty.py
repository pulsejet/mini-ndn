import os
import subprocess
import select
import logging
import msgpack
import pty
import typing
import fcntl
import struct
import termios
import random

from io import TextIOWrapper
from threading import Thread

from mininet.net import Mininet
from mininet.cli import CLI
from minindn.play.cbuf import CircularByteBuffer
from minindn.play.consts import WSKeys, WSFunctions
from minindn.play.socket import PlaySocket
from minindn.util import getPopen
import minindn.play.util as util

class Pty:
    id: str
    name: str
    master: int
    stdin: TextIOWrapper
    thread: Thread
    slave: int
    process: subprocess.Popen = None
    buffer: CircularByteBuffer

    def __init__(self):
        self.master, self.slave = pty.openpty()
        self.buffer = CircularByteBuffer(16000)

    # Send output to UI thread
    @staticmethod
    def ui_out_pty_thread(
        executor,
        id: str, master: int, slave: int,
        proc: subprocess.Popen, buffer: CircularByteBuffer,
    ):
        poller = select.poll()
        poller.register(master, select.POLLIN)
        while not proc or proc.poll() is None:
            if poller.poll(0):
                bytes: bytearray = None
                while poller.poll(1):
                    if not bytes:
                        bytes = bytearray()
                    if len(bytes) >= 4000: # safe MTU
                        break

                    try:
                        read_bytes = os.read(master, 1)
                        bytes.append(read_bytes[0])
                    except OSError:
                        break

                if bytes:
                    executor._send_pty_out(bytes, id)
                    buffer.write(bytes)

        executor.socket.send_all(msgpack.dumps({
            WSKeys.MSG_KEY_FUN: WSFunctions.CLOSE_TERMINAL,
            WSKeys.MSG_KEY_ID: id,
        }))

        os.close(master)
        os.close(slave)
        del executor.pty_list[id]

    def start(self, executor):
        executor.pty_list[self.id] = self
        self.stdin = os.fdopen(self.master, 'wb')
        self.thread = Thread(target=Pty.ui_out_pty_thread,
                             args=(executor, self.id, self.master, self.slave, self.process, self.buffer),
                             daemon=True)
        self.thread.start()

class PtyExecutor:
    net: Mininet = None
    pty_list: typing.Dict[str, Pty] = {}
    socket: PlaySocket = None

    def __init__(self, net: Mininet, socket: PlaySocket):
        self.net = net
        self.socket = socket

    def start_cli(self):
        """UI Function: Start CLI"""
        # Send logs to UI
        class WsCliHandler():
            parent: PtyExecutor = None

            def __init__(self, parent):
                self.parent = parent

            def write(self, msg: str):
                mb = msg.encode('utf-8')
                self.parent._send_pty_out(mb, "cli")
                self.parent.pty_list["cli"].buffer.write(mb)

        lg = logging.getLogger("mininet")
        handler = logging.StreamHandler(WsCliHandler(self))
        handler.terminator = ""
        lg.addHandler(handler)

        # Create pty for cli
        cpty = Pty()
        cpty.id = "cli"
        cpty.name = "MiniNDN CLI"
        cpty.start(self)

        # Start cli
        CLI.use_rawinput = False
        CLI(self.net, stdin=os.fdopen(cpty.slave, 'r'), stdout=os.fdopen(cpty.slave, 'w'))

    async def open_all_ptys(self):
        """UI Function: Open all ptys currently active"""
        for key in self.pty_list:
            cpty = self.pty_list[key]
            self.socket.send_all(msgpack.dumps({
                WSKeys.MSG_KEY_FUN: WSFunctions.OPEN_TERMINAL,
                WSKeys.MSG_KEY_RESULT: self._open_term_response(cpty)
            }))

    async def open_term(self, nodeId: str):
        """UI Function: Open new bash terminal"""
        if not util.is_valid_hostid(self.net, nodeId):
            return

        cpty = Pty()
        cpty.process = getPopen(
            self.net[nodeId], 'bash --login --noprofile',
            envDict={"PS1": "\\u@{}:\\w\\$ ".format(nodeId)},
            stdin=cpty.slave, stdout=cpty.slave, stderr=cpty.slave)

        cpty.id = nodeId + str(int(random.random() * 100000))
        cpty.name = "bash [{}]".format(nodeId)
        cpty.start(self)

        return self._open_term_response(cpty)

    async def pty_in(self, id: str, msg: msgpack.ExtType):
        """UI Function: Send input to pty"""
        if id not in self.pty_list:
            return

        if id == "cli" and msg.data == b'\x03':
            # interrupt
            for node in self.net.hosts:
                if node.waiting:
                    node.sendInt()

        self.pty_list[id].stdin.write(msg.data)
        self.pty_list[id].stdin.flush()

    async def pty_resize(self, ptyid, rows, cols):
        """UI Function: Resize pty"""
        if ptyid not in self.pty_list:
            return

        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(self.pty_list[ptyid].master, termios.TIOCSWINSZ, winsize)

    def _send_pty_out(self, msg: bytes, id: str):
        """Send output to UI"""
        self.socket.send_all(msgpack.dumps({
            WSKeys.MSG_KEY_FUN: WSFunctions.PTY_OUT,
            WSKeys.MSG_KEY_ID: id,
            WSKeys.MSG_KEY_RESULT: msg,
        }))

    def _open_term_response(self, cpty: Pty):
        """Return response for open terminal"""
        return { 'id': cpty.id, 'name': cpty.name, 'buf': cpty.buffer.read() }