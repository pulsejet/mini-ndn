#!/usr/bin/env python3

# WS server

# General
from io import TextIOWrapper
from pathlib import Path
from mininet.link import Link
from mininet.log import info, debug, error
from mininet.cli import CLI
from minindn.minindn import Minindn
from minindn.util import getPopen
from threading import Thread
from minindn.play.consts import WSFunctions, WSKeys
from minindn.play.cbuf import CircularByteBuffer
import mininet
import typing
import time

# Messaging
import asyncio
import websockets
import msgpack
import random
import secrets
import urllib

# PTY
import select
import os
import logging
import subprocess
import pty
import fcntl
import struct
import termios

# Constants
AUTH_TOKEN = None
AUTH_FILE = "/tmp/minindn-auth"
PLAY_URL = "https://play.ndn.today"
SERVER_HOST = "0.0.0.0"
SERVER_HOST_URL = "127.0.0.1"
SERVER_PORT = 8765
PCAP_CHUNK_SIZE = 512

# TShark fields
SHARK_FIELDS = [
    "frame.number",
    "frame.time_epoch",
    "ndn.len",
    "ndn.type",
    "ndn.name",
    "ip.src",
    "ip.dst",
    # "ndn.bin", # binary data
]
SHARK_FIELDS_STR = " -Tfields -e " + " -e ".join(SHARK_FIELDS) + " -Y ndn.len"

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
                    read_bytes = os.read(master, 1)
                    bytes.append(read_bytes[0])
                if bytes:
                    _send_pty_out(bytes, id)
                    buffer.write(bytes)

        _send_threadsafe_all(msgpack.dumps({
            WSKeys.MSG_KEY_FUN: WSFunctions.CLOSE_TERMINAL,
            WSKeys.MSG_KEY_ID: id,
        }))

        os.close(master)
        os.close(slave)
        del pty_list[id]

    def start(self):
        pty_list[self.id] = self
        self.stdin = os.fdopen(self.master, 'wb')
        self.thread = Thread(target=Pty.ui_out_pty_thread,
                             args=(self.id, self.master, self.slave, self.process, self.buffer),
                             daemon=True)
        self.thread.start()

# Globals
ndn_net: Minindn = None
conn_list = {}
pty_list: typing.Dict[str, Pty] = {}
c_loop: asyncio.AbstractEventLoop = None

def _get_pcap_file(name):
    return '{}{}-interfaces.pcap'.format('./', name)

def _send_threadsafe(websocket, msg):
    """Send message to UI threadsafe"""
    if websocket.open:
        c_loop.call_soon_threadsafe(c_loop.create_task, websocket.send(msg))

def _send_threadsafe_all(msg):
    """Send message to all UI threadsafe"""
    for websocket in conn_list:
        try:
            _send_threadsafe(websocket, msg)
        except:
            del conn_list[websocket]

def _is_valid_hostid(nodeId: str):
    """Check if a nodeId is a host"""
    if nodeId not in ndn_net:
        return False
    if not isinstance(ndn_net[nodeId], mininet.node.Host):
        return False
    return True

def _conv_link_opts(opts):
    """Helper: convert link options"""
    params = {}
    if 'latency' in opts and opts['latency'] is not None:
        params['delay'] = str(opts['latency']) + 'ms'
    if 'loss' in opts and opts['loss'] is not None:
        params['loss'] = float(opts['loss'])
    return params

def _get_link(a, b, mnId) -> Link:
    """Helper: get link between two nodes by name"""
    for link in ndn_net.linksBetween(ndn_net[a], ndn_net[b]):
        if str(link) == mnId:
            return link

    return None

def _run_popen(node, cmd):
    """Helper to run command on node asynchronously and get output"""
    process = getPopen(node, cmd, stdout=subprocess.PIPE)
    return process.communicate()[0]

def _run_popen_readline(node, cmd):
    """Helper to run command on node asynchronously and get output line by line"""
    process = getPopen(node, cmd, stdout=subprocess.PIPE)
    while True:
        line = process.stdout.readline()
        if not line:
            break
        yield line

def _get_ip_map():
    """Get IP address map for all links in net"""
    addresses = {}
    def addIntf(intf):
        addresses[intf.ip] = intf.node.name
    for link in ndn_net.links:
        addIntf(link.intf1)
        addIntf(link.intf2)

    return addresses

def _host_home(node):
    """Get home directory for host"""
    return node.params['params']['homeDir']

async def get_topo():
    """UI Function: Get topology"""
    nodes = []
    links = []

    for host in ndn_net.hosts:
        nodes.append({
            'id': host.name,
            'label': host.name,
        })

    for switch in ndn_net.switches:
        nodes.append({
            'id': switch.name,
            'label': switch.name,
            'isSwitch': True,
        })

    for link in ndn_net.links:
        obj = {
            'mnId': str(link),
            'from': link.intf1.node.name,
            'to': link.intf2.node.name,
        }

        if 'delay' in link.intf1.params:
            d1 = int(link.intf1.params['delay'][:-len('ms')])
            d2 = int(link.intf2.params['delay'][:-len('ms')])
            obj['latency'] = (d1 + d2) / 2

        if 'loss' in link.intf1.params:
            l1 = link.intf1.params['loss']
            l2 = link.intf2.params['loss']
            obj['loss'] = (l1 + l2) / 2

        links.append(obj)

    return {
        'nodes': nodes,
        'links': links,
    }

async def open_all_ptys():
    """UI Function: Open all ptys currently active"""
    for key in pty_list:
        cpty = pty_list[key]
        for websocket in conn_list:
            try:
                await websocket.send(msgpack.dumps({
                                WSKeys.MSG_KEY_FUN: WSFunctions.OPEN_TERMINAL,
                                WSKeys.MSG_KEY_RESULT: _open_term_response(cpty)
                }))
            except:
                del conn_list[websocket]

async def del_link(a, b, mnId):
    """UI Function: Delete link"""
    link = _get_link(a, b, mnId)
    if link:
        ndn_net.delLink(link)
        ndn_net.configHosts()
        return True

    error('No link found to remove for {}\n'.format(mnId))
    return False

async def add_link(a, b, id, opts):
    """UI Function: Add link"""
    link = ndn_net.addLink(ndn_net[a], ndn_net[b], **_conv_link_opts(opts))
    ndn_net.configHosts()
    info('Added link {}\n'.format(link))
    return {
        'id': id,
        'mnId': str(link),
        **opts,
    }

async def upd_link(a, b, mnId, opts):
    """UI Function: Update link"""
    link = _get_link(a, b, mnId)
    if link:
        params = _conv_link_opts(opts)
        link.intf1.config(**params)
        link.intf2.config(**params)
        for p in params:
            link.intf1.params[p] = params[p]
            link.intf2.params[p] = params[p]
        return True

    info('No link to configure for {}\n'.format(mnId))
    return False

async def del_node(a):
    """UI Function: Delete node"""
    ndn_net.delNode(ndn_net[a])
    ndn_net.configHosts()
    info('Removed node {}\n'.format(a))
    return True

async def add_node(id, label):
    """UI Function: Add node (host is added)"""
    ndn_net.addHost(label)
    ndn_net.configHosts()
    return {
        'id': id,
        'label': label,
    }

async def get_fib(nodeId):
    """UI Function: Get the NFDC status report and ifconfig as the fib"""
    if not _is_valid_hostid(nodeId):
        if nodeId in ndn_net:
            node = ndn_net[nodeId]
            return { 'id': nodeId, 'fib': "Node is not a host ({})".format(node.__class__.__name__) }
        return

    node = ndn_net[nodeId]
    nfd_status = _run_popen(node, "nfdc status report".split()).decode('utf-8')
    ifconfig = _run_popen(node, "ifconfig".split()).decode('utf-8')
    output = nfd_status + "\n" + ifconfig
    return {
        'id': nodeId,
        'fib': output,
    }

def _get_lua():
    luafile = str(Path(__file__).parent.absolute()) + '/ndn.lua'
    return 'lua_script:' + luafile

def _send_pcap_chunks(nodeId: str, known_frame: int, include_wire: bool):
    """
    Get, process and send chunks of pcap to UI
    Blocking; should run in its own thread.
    """

    node = ndn_net[nodeId]
    file = _get_pcap_file(nodeId)

    # We don't want to load and process the entire pcap file
    # every time the user wants to recheck. Instead, use editcap
    # to cut the part the user knows

    # Look back by upto 12 frames in case the last packet was fragmented
    known_frame = max(1, known_frame - 12)

    # Get everything after known frame
    editcap_cmd = "editcap -r {} {} {}-0".format(file, "/dev/stdout", known_frame)

    # Shark using NDN dissector
    extra_fields = "-e ndn.bin " if include_wire else ""
    list_cmd = 'tshark {} {} -r {} -X {}'.format(SHARK_FIELDS_STR, extra_fields, "/dev/stdin", _get_lua())

    # Pipe editcap to tshark
    piped_cmd = ['bash', '-c', '{} | {}'.format(editcap_cmd, list_cmd)]

    # Map for source and destination nodes
    ip_map = _get_ip_map()

    # Collected packets (one chunk)
    packets = []

    def _send_packets(last=False):
        """Send the current chunk to the UI (including empty)"""
        res = {
            'id': nodeId,
            'packets': packets,
        }
        if last:
            res['last'] = True

        _send_threadsafe_all(msgpack.dumps({
            WSKeys.MSG_KEY_FUN: WSFunctions.GET_PCAP,
            WSKeys.MSG_KEY_RESULT: res,
        }))

    # Iterate each line of output
    for line in _run_popen_readline(node, piped_cmd):
        line = line.decode('utf-8').strip().split()

        if len(line) < 6:
            continue

        packets.append([
            int(line[0]) + known_frame - 1, # frame number
            float(line[1]) * 1000, # timestamp
            int(line[2]), # length
            line[3], # type
            line[4], # NDN name
            ip_map.get(line[5], line[5]), # from
            ip_map.get(line[6], line[6]), # to
            bytes.fromhex(line[7]) if include_wire else 0, # packet content
        ])

        if len(packets) >= PCAP_CHUNK_SIZE:
            _send_packets()
            packets = []

    # Send the last chunk
    _send_packets(last=True)

async def get_pcap(nodeId: str, known_frame: int, include_wire=False):
    """UI Function: Get list of packets for one node"""
    if not _is_valid_hostid(nodeId):
        return

    # Run processing in separate thread
    t = Thread(target=_send_pcap_chunks, args=(nodeId, known_frame, include_wire), daemon=True)
    t.start()

async def get_pcap_wire(nodeId, frame):
    """UI Function: Get wire of one packet"""
    if not _is_valid_hostid(nodeId):
        return
    file = _get_pcap_file(nodeId)

    # chop the file to the frame
    # include the last 12 frames in case of fragmentation
    start_frame = max(1, frame - 12)
    new_frame = frame - start_frame + 1

    try:
        # Get last 12 frames
        editcap_cmd = "editcap -r {} {} {}-{}".format(file, "/dev/stdout", start_frame, frame)

        # Filter for this packet only
        wire_cmd = 'tshark -r {} -e ndn.bin -Tfields -X {} frame.number == {}'.format('-', _get_lua(), new_frame)

        # Pipe editcap to tshark
        piped_cmd = ['bash', '-c', '{} | {}'.format(editcap_cmd, wire_cmd)]
        hex = _run_popen(ndn_net[nodeId], piped_cmd).decode('utf-8').strip()
        return bytes.fromhex(hex)
    except Exception:
        error('Error getting pcap wire for {}'.format(nodeId))

async def pty_in(id, msg: msgpack.ExtType):
    """UI Function: Send input to pty"""
    if id not in pty_list:
        return

    if id == "cli" and msg.data == b'\x03':
        # interrupt
        for node in ndn_net.hosts:
            if node.waiting:
                node.sendInt()

    pty_list[id].stdin.write(msg.data)
    pty_list[id].stdin.flush()

def _open_term_response(cpty: Pty):
    """Return response for open terminal"""
    return { 'id': cpty.id, 'name': cpty.name, 'buf': cpty.buffer.read() }

async def open_term(nodeId):
    """UI Function: Open new bash terminal"""
    if not _is_valid_hostid(nodeId):
        return

    cpty = Pty()
    cpty.process = getPopen(
        ndn_net[nodeId], 'bash --login --noprofile',
        envDict={"PS1": "\\u@{}:\\w\\$ ".format(nodeId)},
        stdin=cpty.slave, stdout=cpty.slave, stderr=cpty.slave)

    cpty.id = nodeId + str(int(random.random() * 100000))
    cpty.name = "bash [{}]".format(nodeId)
    cpty.start()

    return _open_term_response(cpty)

async def pty_resize(ptyid, rows, cols):
    """UI Function: Resize pty"""
    if ptyid not in pty_list:
        return

    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(pty_list[ptyid].master, termios.TIOCSWINSZ, winsize)

def _send_pty_out(msg: bytes, id: str):
    """Send output to UI"""
    _send_threadsafe_all(msgpack.dumps({
        WSKeys.MSG_KEY_FUN: WSFunctions.PTY_OUT,
        WSKeys.MSG_KEY_ID: id,
        WSKeys.MSG_KEY_RESULT: msg,
    }))

async def _call_fun(websocket, fcall):
    """Call function and return result to UI asynchronously"""
    res = await globals()[fcall[WSKeys.MSG_KEY_FUN]](*fcall[WSKeys.MSG_KEY_ARGS])
    if res is not None:
        pack = msgpack.dumps({
            WSKeys.MSG_KEY_FUN: fcall[WSKeys.MSG_KEY_FUN],
            WSKeys.MSG_KEY_RESULT: res,
        })
        await websocket.send(pack)

async def _serve_ws(websocket, path):
    """Handle websocket connection"""
    try:
        auth = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)['auth'][0]
        if auth != AUTH_TOKEN:
            raise Exception("Invalid auth token")
    except:
        print('Rejected connection from {}'.format(websocket.remote_address))
        await websocket.close()
        return

    print('Accepted connection from {}'.format(websocket.remote_address))
    conn_list[websocket] = 1
    while True:
        try:
            fcall = msgpack.loads(await websocket.recv())
            loop = asyncio.get_event_loop()
            loop.create_task(_call_fun(websocket, fcall))
        except websockets.exceptions.ConnectionClosedOK:
            print('Closed connection gracefully from {}'.format(websocket.remote_address))
            break
        except websockets.exceptions.ConnectionClosedError:
            print('Closed connection with error from {}'.format(websocket.remote_address))
            break

    del conn_list[websocket]

def _start_background_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Runs in separate thread from main"""
    global c_loop
    c_loop = loop

    # Show the URL to the user
    ws_url = "ws://{}:{}".format(SERVER_HOST_URL, SERVER_PORT)
    ws_url_q = urllib.parse.quote(ws_url.encode('utf8'))
    full_url = "{}/?minindn={}&auth={}".format(PLAY_URL, ws_url_q, AUTH_TOKEN)
    print('Open NDN Play GUI at {}'.format(full_url))

    # Start server
    asyncio.set_event_loop(loop)
    start_server = websockets.serve(_serve_ws, SERVER_HOST, SERVER_PORT)
    loop.run_until_complete(start_server)
    loop.run_forever()

def StartPlayServer(m_ndn_net, cli=True):
    """
    Start NDN Play GUI server.
    If cli=True is specified (default), will block for the MiniNDN CLI.
    """
    global ndn_net
    global AUTH_TOKEN
    ndn_net = m_ndn_net

    # Perist auth token so you don't need to refresh every time
    # Check if AUTH_FILE was modified less than a day ago
    if os.path.exists(AUTH_FILE) and time.time() - os.path.getmtime(AUTH_FILE) < 24 * 60 * 60:
        with open(AUTH_FILE, 'r') as f:
            AUTH_TOKEN = f.read().strip()
            debug('Restoring AUTH_TOKEN')

    if not AUTH_TOKEN or len(AUTH_TOKEN) < 10:
        AUTH_TOKEN = secrets.token_hex(16)
        with open(AUTH_FILE, 'w') as f:
            f.write(AUTH_TOKEN)
            debug('Persisting AUTH_TOKEN for a day')

    # Start loop thread
    loop = asyncio.new_event_loop()
    t = Thread(target=_start_background_loop, args=(loop,), daemon=True)
    t.start()

    if cli:
        # Send logs to UI
        class WsCliHandler():
            def write(self, msg: str):
                mb = msg.encode('utf-8')
                _send_pty_out(mb, "cli")
                pty_list["cli"].buffer.write(mb)

        lg = logging.getLogger("mininet")
        handler = logging.StreamHandler(WsCliHandler())
        handler.terminator = ""
        lg.addHandler(handler)

        # Create pty for cli
        cpty = Pty()
        cpty.id = "cli"
        cpty.name = "MiniNDN CLI"
        cpty.start()

        # Start cli
        CLI.use_rawinput = False
        CLI(ndn_net, stdin=os.fdopen(cpty.slave, 'r'), stdout=os.fdopen(cpty.slave, 'w'))
