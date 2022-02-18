import asyncio
from kademlia.network import Server

from core.config import Config


class P2p(object):
    def __init__(self):
        self.server = Server()
        self.loop = None

    def run(self):
        port = int(Config().get('node.listen_port'))
        loop = asyncio.get_event_loop()
        self.loop = loop
        loop.run_until_complete(self.server.listen(port))
        self.loop.run_until_complete(self.server.bootstrap([(
            Config().get('node.bootstrap_host'), port)]))
        loop.run_forever()

    def get_nodes(self):
        nodes = []
        for bucket in self.server.protocol.router.buckets:
            nodes.extend(bucket.get_nodes())
        return nodes
