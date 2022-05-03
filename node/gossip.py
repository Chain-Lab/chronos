import json
import logging
import random
import threading
import socket
import time

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
        self.server_thread = threading.Thread(target=self.server, args=(), name="UDP Server")
        self.client_thread = threading.Thread(target=self.__task, args=(), name="UDP Client")

    def run(self):
        self.server_thread.start()
        self.client_thread.start()

    def server(self):
        logging.debug("UDP Server start")
        local_ip = Config().get('node.listen_ip')
        port = Config().get('node.gossip_port')
        addr = (local_ip, int(port))

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(addr)

        while True:
            data, addr = s.recvfrom(20480)           # 15kb
            logging.debug("Receive transaction from {}.".format(addr))
            try:
                data = json.loads(data.decode())
            except json.JSONDecodeError:
                logging.error("Receive wrong data.")
                continue

            logging.debug(data)
            if not json_validator("./schemas/transaction.json", data):
                logging.error("Receive transaction invalid.")
                continue

            tx = Transaction.deserialize(data)
            self.append(tx)
            time.sleep(3)
            # 等待3s， gossip发送交易太快了占用cpu较多

    def append(self, tx: Transaction):
        if TxMemPool().add(tx):
            logging.debug("Append transaction to queue.")
            with self.__cond:
                self.__queue.append(tx)
                self.__cond.notify_all()

    def __task(self):
        logging.debug("UDP Client start")
        local_ip = Config().get('node.listen_ip')
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        while True:
            with self.__cond:
                while not len(self.__queue) or len(Peer().nodes) == 0:
                    logging.debug("Client wait insert new transaction.")
                    self.__cond.wait()

                tx: Transaction
                tx = self.__queue.pop()
                logging.debug("Client pop transaction.")

                data = json.dumps(tx.serialize())
                length = len(Peer().nodes)

                nodes = random.choices(Peer().nodes, k=length // 2)
                logging.info("Send tx to gossip network.")
                for node in nodes:
                    ip = node.ip
                    port = Config().get('node.gossip_port')

                    if ip == local_ip:
                        continue

                    addr = (ip, int(port))
                    # UDPConnect.send_msg(s, addr, data)
                    s.sendto(data.encode(), addr)
                    time.sleep(1)