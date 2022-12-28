import logging
import threading
import time

from core.config import Config
from node.client import Client
from utils.singleton import Singleton
from utils import constant


class Peer(Singleton):
    def __init__(self, manager):
        # 消除多次__init__问题后可以直接初始化
        self.peers = []
        self.nodes = []
        self.manager = manager

    def find_nodes(self, p2p_server):
        # local_ip = socket.getaddrinfo(socket.gethostname(), None)
        local_ip = Config().get('node.listen_ip')

        logging.debug("Local ip address is: {}".format(local_ip))

        while True:
            if not constant.NODE_RUNNING:
                logging.debug("Receive stop signal, stop thread.")
                break

            nodes = p2p_server.get_nodes()
            for node in nodes:
                if node not in self.nodes:
                    ip = node.ip
                    port = node.port

                    # todo: 判定自身ip的存在问题， 需要修改
                    if ip == local_ip:
                        continue
                    logging.info("Detect new node: ip {} port {}".format(ip, port))
                    client = Client(ip, port, self.manager)
                    thread = threading.Thread(target=client.shake_loop)
                    thread.start()
                    self.peers.append(client)
                    self.nodes.append(node)
            time.sleep(1)
    @property
    def clients(self):
        return self.peers

    def run(self, p2p_server):
        thread = threading.Thread(target=self.find_nodes, args=(p2p_server,))
        thread.start()
