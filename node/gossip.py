import json
import logging
import random
import socket
import threading
import time
from queue import Queue

from core.config import Config
from core.transaction import Transaction
from core.txmempool import TxMemPool
from node.peer import Peer
from node.manager import Manager
from utils.locks import package_cond, package_lock
from utils.singleton import Singleton
from utils.validator import json_validator

from utils import constant


class Gossip(Singleton):
    def __init__(self):
        self.__queue = Queue()
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
            if not constant.NODE_RUNNING:
                logging.debug("Receive stop signal, stop thread.")
                break

            # 如果当前有线程在打包区块， 让出CPU资源
            with package_cond:
                while package_lock.locked():
                    logging.debug("Wait block package finished.")
                    package_cond.wait()

            # 接收最大15kb的数据
            data, addr = s.recvfrom(65535)  # 64kb
            logging.debug("Receive transaction from {}.".format(addr))
            try:
                # 检查是否能够经过json序列化
                data = json.loads(data.decode())
            except json.JSONDecodeError:
                logging.error("Receive wrong data.")
                continue

            # 使用交易的json格式进行验证
            # if not json_validator("./schemas/transaction_v2.json", data):
            #     logging.error("Receive transaction invalid.")
            #     continue

            tx = Transaction.deserialize(data)
            # 添加交易到交易池和Client的队列
            self.append(tx)
            # time.sleep(0.01)
            # 等待1s， 避免gossip发送交易太快了占用cpu较多

    def append(self, tx: Transaction):
        if TxMemPool().add(tx):
            logging.debug("Append transaction to queue.")
            with self.__cond:
                self.__queue.put(tx)
                self.__cond.notify_all()

    def __task(self):
        logging.debug("UDP Client start")
        local_ip = Config().get('node.listen_ip')
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        while True:
            if not constant.NODE_RUNNING:
                logging.debug("Receive stop signal, stop thread.")
                break

            # 如果有区块正在打包， 等待打包完成
            with package_cond:
                while package_lock.locked():
                    logging.debug("Wait block package finished.")
                    package_cond.wait()

            with self.__cond:
                # 条件锁，等待唤醒
                while self.__queue.empty() or len(Peer(Manager()).nodes) == 0:
                    logging.debug("Client wait insert new transaction.")
                    self.__cond.wait()

                tx: Transaction
                tx = self.__queue.get()
                logging.debug("Client pop transaction.")

                data = json.dumps(tx.serialize())
                length = len(Peer(Manager()).nodes)

                # 选取50%的邻居节点发送交易
                nodes = random.choices(Peer(Manager()).nodes, k=length // 2)
                logging.debug("Send tx to gossip network.")
                for node in nodes:
                    ip = node.ip
                    port = Config().get('node.gossip_port')

                    if ip == local_ip:
                        continue

                    addr = (ip, int(port))
                    # UDPConnect.send_msg(s, addr, data)
                    try:
                        s.sendto(data.encode(), addr)
                    except OSError:
                        logging.error("Message too long.")
                        break
                # time.sleep(0.01)

    @property
    def queue_size(self):
        return self.__queue.qsize()
