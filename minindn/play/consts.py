from enum import Enum

# MessagePack Keys
class WSKeys(str, Enum):
    MSG_KEY_FUN = 'F'
    MSG_KEY_ID = 'I'
    MSG_KEY_RESULT = 'R'
    MSG_KEY_ARGS = 'A'

class WSFunctions(str, Enum):
    GET_TOPO = 'get_topo'
    OPEN_ALL_PTYS = 'open_all_ptys'
    DEL_LINK = 'del_link'
    ADD_LINK = 'add_link'
    UPD_LINK = 'upd_link'
    DEL_NODE = 'del_node'
    ADD_NODE = 'add_node'
    GET_FIB = 'get_fib'
    GET_PCAP = 'get_pcap'
    GET_PCAP_WIRE = 'get_pcap_wire'
    PTY_IN = 'pty_in'
    PTY_OUT = 'pty_out'
    PTY_RESIZE = 'pty_resize'
    OPEN_TERMINAL = 'open_term'
    CLOSE_TERMINAL = 'close_term'