import os
import logging
import msgpack
import typing
import fcntl
import struct
import termios
import random

from mininet.net import Mininet
from mininet.cli import CLI
from minindn.play.consts import WSKeys, WSFunctions
from minindn.play.socket import PlaySocket
from minindn.play.term.pty import Pty
from minindn.util import getPopen
import minindn.play.util as util

class TermExecutor:
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
            parent: TermExecutor = None

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
        cpty = Pty(self)
        cpty.id = "cli"
        cpty.name = "MiniNDN CLI"
        cpty.start()

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

        cpty = Pty(self)
        cpty.process = getPopen(
            self.net[nodeId], 'bash --login --noprofile',
            envDict={"PS1": "\\u@{}:\\w\\$ ".format(nodeId)},
            stdin=cpty.slave, stdout=cpty.slave, stderr=cpty.slave)

        cpty.id = nodeId + str(int(random.random() * 100000))
        cpty.name = "bash [{}]".format(nodeId)
        cpty.start()

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