import json
import logging
import random
import threading
import socket

from core.config import Config
from core.transaction import Transaction
from core.txmempool import TxMemPool
from node.peer import Peer
from utils.singleton import Singleton
from utils.validator import json_validator


class Gossip(Singleton):
    def __init__(self):
        self.__queue = []
        self.__cond = threading.Condition()

    def run(self):
        pass

    def server(self):
        local_ip = Config().get('node.listen_ip')
        port = Config().get('node.gossip_port')
        addr = (local_ip, port)

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(addr)

        while True:
            data, addr = s.recvfrom(15360)           # 15kb
            logging.debug("Receive transaction from {}.".format(addr))
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                logging.error("Receive wrong data.")
                continue

            tx = Transaction.deserialize(data)
            if not json_validator("./schemas/transaction.json", tx):
                logging.error("Receive transaction invalid.")
                continue

            self.append(tx)

    def append(self, tx):
        if TxMemPool().add(tx):
            logging.debug("Append transaction to queue.")
            self.__queue.append(tx)
            self.__cond.notify_all()

    def __task(self):
        local_ip = Config().get('node.listen_ip')
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        while True:
            with self.__cond:
                length = len(Peer().nodes)
                while not len(self.__queue) or length == 0:
                    self.__cond.wait()

                tx: Transaction
                tx = self.__queue.pop()
                data = json.dumps(tx.serialize())

                nodes = random.choices(Peer().nodes, k=length // 2)
                logging.info("Send tx to gossip network.")
                for node in nodes:
                    ip = node.ip
                    port = Config().get('node.gossip_port')

                    if ip == local_ip:
                        continue

                    addr = (ip, port)
                    # UDPConnect.send_msg(s, addr, data)
                    s.sendto(data.encode(), addr)
