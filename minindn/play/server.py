from threading import Thread
from minindn.play.socket import PlaySocket
from minindn.play.net.topo import TopoExecutor
from minindn.play.net.state import StateExecutor
from minindn.play.term.term import TermExecutor
from minindn.play.shark.shark import SharkExecutor
from mininet.net import Mininet

class PlayServer:
    net: Mininet = None

    def __init__(self, net: Mininet, cli=True, repl=False) -> None:
        """
        Start NDN Play GUI server.
        If cli=True is specified (default), will block for the MiniNDN CLI.
        """

        self.net = net

        self.socket = PlaySocket()
        self.socket.add_executor(TopoExecutor(net))
        self.socket.add_executor(StateExecutor(net))

        shark_executor = SharkExecutor(net, self.socket)
        self.socket.add_executor(shark_executor)

        pty_executor = TermExecutor(net, self.socket)
        self.socket.add_executor(pty_executor)

        if repl:
            Thread(target=pty_executor.start_repl).start()

        if cli:
            pty_executor.start_cli()
