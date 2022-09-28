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
        # 这里是否bootstrap的区别在于： 如果没有其他的节点，那么将本地作为一个初始的p2p索引服务器，其他节点需要先连接该节点进行同步
        # 如果存在其他的已有的服务器的情况下不再需要bootstrap，可以直接已有的节点
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
        try:
            self_node = self.server.protocol.source_node
            return self.server.protocol.router.find_neighbors(self_node)
        except AttributeError:
            logging.error("Route table is not initialization.")
            return []