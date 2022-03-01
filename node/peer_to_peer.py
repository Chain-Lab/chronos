import asyncio
import logging

from kademlia.network import Server

from core.config import Config


class P2p(object):
    def __init__(self):
        self.server = Server()
        self.loop = None

    def run(self):
        port = int(Config().get('node.listen_port'))
        bootstrap = int(Config().get('node.is_bootstrap'))
        if bootstrap:
            host = Config().get('node.listen_ip')
        else:
            host = Config().get('node.bootstrap_host')

        logging.info("Start p2p bootstrap server to ip: {} port: {}".format(host, port))
        loop = asyncio.get_event_loop()
        self.loop = loop
        loop.run_until_complete(self.server.listen(port))
        self.loop.run_until_complete(self.server.bootstrap([(host, port)]))
        loop.run_forever()

    def get_nodes(self):
        nodes = []
        try:
            for bucket in self.server.protocol.router.buckets:
                nodes.extend(bucket.get_nodes())
        except AttributeError:
            logging.error("Router is NoneType.")
        return nodes
