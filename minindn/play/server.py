from minindn.play.socket import PlaySocket
from minindn.play.topo import TopoExecutor
from minindn.play.pty import PtyExecutor
from minindn.play.state import StateExecutor
from minindn.play.shark import SharkExecutor
from mininet.net import Mininet

class PlayServer:
    net: Mininet = None

    def __init__(self, net: Mininet, cli=True) -> None:
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

        pty_executor = PtyExecutor(net, self.socket)
        self.socket.add_executor(pty_executor)

        if cli:
            pty_executor.start_cli()
