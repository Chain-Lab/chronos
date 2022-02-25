import logging
import socket
import threading
import time

from node.client import Client
from utils.singleton import Singleton
from core.config import Config


class Peer(Singleton):
    def __init__(self):
        if not hasattr(self, 'peers'):
            self.peers = []
        if not hasattr(self, 'nodes'):
            self.nodes = []

    def find_nodes(self, p2p_server):
        # local_ip = socket.gethostbyname(socket.getfqdn(socket.gethostname()))
        local_ip = Config().get('node.listen_ip')
        logging.debug("Local ip address is: {}".format(local_ip))

        while True:
            nodes = p2p_server.get_nodes()
            for node in nodes:
                if node not in self.nodes:
                    ip = node.ip
                    port = node.port
                    time.sleep(0.5)
                    if local_ip == ip:
                        continue
                    # todo: 自身节点的判断方法存在问题
                    logging.info("Detect new node: ip {} port {}".format(ip, port))
                    client = Client(ip, port)
                    thread = threading.Thread(target=client.shake_loop)
                    thread.start()
                    self.peers.append(client)
                    self.nodes.append(node)
            time.sleep(1)

    def broadcast(self, transaction):
        peer: Client

        for peer in self.peers:
            peer.add_transaction(transaction)

    def search(self):
        pass

    def run(self, p2p_server):
        thread = threading.Thread(target=self.find_nodes, args=(p2p_server,))
        thread.start()
