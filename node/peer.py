import socket
import threading
import time

from utils.singleton import Singleton
from core.config import Config
from node.client import Client


class Peer(Singleton):
    def __init__(self):
        if not hasattr(self, 'peers'):
            self.peers = []
        if not hasattr(self, 'nodes'):
            self.nodes = []

    def find_nodes(self, p2p_server):
        local_ip = socket.gethostbyname(socket.getfqdn(socket.gethostname()))

        while True:
            nodes = p2p_server.get_nodes()
            for node in nodes:
                if node not in self.nodes:
                    ip = node.ip
                    port = node.port

                    if local_ip == ip:
                        continue

                    client = Client(ip, port)
                    thread = threading.Thread(target=client.shake_loop)
                    thread.start()
                    self.peers.append(client)
                    self.nodes.append(node)
            time.sleep(1)

    def broadcast(self, transaction):
        for peer in self.peers:
            peer.add_tx(transaction)

    def search(self):
        pass

    def run(self, p2p_server):
        thread = threading.Thread(target=self.find_nodes, args=(p2p_server, ))
        thread.start()