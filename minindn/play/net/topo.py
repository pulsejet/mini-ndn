from mininet.net import Mininet
from mininet.log import info, debug, error
from mininet.link import Link

class TopoExecutor:
    net: Mininet = None

    def __init__(self, net: Mininet):
        self.net = net

    async def get_topo(self):
        """UI Function: Get topology"""
        nodes = []
        links = []

        hosts = self.net.hosts.copy()
        if hasattr(self.net, 'stations'):
            hosts += self.net.stations
        if hasattr(self.net, 'cars'):
            hosts += self.net.cars

        for host in hosts:
            nodes.append({
                'id': host.name,
                'label': host.name,
            })

        for switch in self.net.switches:
            nodes.append({
                'id': switch.name,
                'label': switch.name,
                'isSwitch': True,
            })

        for link in self.net.links:
            if isinstance(link.intf2, str):
                if link.intf2 == 'wifiAdhoc':
                    # TODO: visualize adhoc links
                    pass
                continue

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

    async def add_link(self, a, b, id, opts):
        """UI Function: Add link"""
        link = self.net.addLink(self.net[a], self.net[b], **self._conv_link_opts(opts))
        self.net.configHosts()
        info('Added link {}\n'.format(link))
        return {
            'id': id,
            'mnId': str(link),
            **opts,
        }

    async def del_link(self, a, b, mnId):
        """UI Function: Delete link"""
        link = self._get_link(a, b, mnId)
        if link:
            self.net.delLink(link)
            self.net.configHosts()
            return True

        error('No link found to remove for {}\n'.format(mnId))
        return False

    async def upd_link(self, a, b, mnId, opts):
        """UI Function: Update link"""
        link = self._get_link(a, b, mnId)
        if link:
            params = self._conv_link_opts(opts)
            link.intf1.config(**params)
            link.intf2.config(**params)
            for p in params:
                link.intf1.params[p] = params[p]
                link.intf2.params[p] = params[p]
            return True

        info('No link to configure for {}\n'.format(mnId))
        return False

    async def add_node(self, id, label):
        """UI Function: Add node (host is added)"""
        self.net.addHost(label)
        self.net.configHosts()
        return {
            'id': id,
            'label': label,
        }

    async def del_node(self, id):
        """UI Function: Delete node"""
        self.net.delNode(self.net[id])
        self.net.configHosts()
        info('Removed node {}\n'.format(id))
        return True

    def _get_link(self, a, b, mnId) -> Link:
        """Helper: get link between two nodes by name"""
        for link in self.net.linksBetween(self.net[a], self.net[b]):
            if str(link) == mnId:
                return link

        return None

    def _conv_link_opts(self, opts: dict):
        """Helper: convert link options"""
        params = {}
        if 'latency' in opts and opts['latency'] is not None:
            params['delay'] = str(opts['latency']) + 'ms'
        if 'loss' in opts and opts['loss'] is not None:
            params['loss'] = float(opts['loss'])
        return params
