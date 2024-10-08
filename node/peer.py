import logging
import threading
import time

from core.config import Config
from node.client import Client
from utils.singleton import Singleton
from utils import constant


class Peer(Singleton):
    def __init__(self):
        # 消除多次__init__问题后可以直接初始化
        self.peers = []
        self.nodes = []

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
                    client = Client(ip, port)
                    thread = threading.Thread(target=client.shake_loop)
                    thread.start()
                    self.peers.append(client)
                    self.nodes.append(node)
            time.sleep(1)

    def broadcast(self, transaction):
        """
        待改造，节点直接通过UDP-gossip协议来进行交易的传播
        :param transaction:
        :return:
        """
        peer: Client
        logging.debug("Peer start broadcast transaction")

        for peer in self.peers:
            peer.add_transaction(transaction)

    def search(self):
        pass

    def run(self, p2p_server):
        thread = threading.Thread(target=self.find_nodes, args=(p2p_server,))
        thread.start()
