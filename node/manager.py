import queue
import random
import threading
import logging
from math import sqrt

from lru import LRU

from node.peer import Peer
from node.timer import Timer
from threads.calculator import Calculator
from utils import funcs
from utils.locks import package_lock, package_cond
from core.block_chain import BlockChain
from threads.selector import Selector
from utils.singleton import Singleton


class Manager(Singleton):
    def __init__(self):
        # 待广播的区块和区块的哈希值
        self.__queued_block = queue.Queue()
        self.__known_block = LRU(1024)
        self.__append_lock = threading.Lock()
        self.__insert_lock = threading.Lock()
        self.__cond = threading.Condition()
        self.__await_block_count = 0
        self.thread = threading.Thread(target=self.task, name="Manager Thread")
        self.thread.start()

    def task(self):
        while True:
            with self.__cond:
                while self.__queued_block.empty():
                    logging.debug("Manager wait for new block.")
                    self.__cond.wait()

                block = self.__queued_block.get()
                Selector().compare_block(block)
                self.__broadcast(block)

    def insert_block(self, block):
        """
        插入新的区块，这里的区块在其他节点上已经被确认放入数据库

        Args:
            block: 新插入的区块
        """
        block_hash = block.hash
        block_height = block.height

        with self.__insert_lock:
            if block_height != BlockChain().latest_height + 1:
                return

            # 在同一时间只能有一个线程插入区块
            self.__known_block[block_hash] = block
            Selector().refresh(block.height)
            BlockChain().insert_block(block)
            Timer().refresh()
            delay_params = block.transactions[0].delay_params
            hex_seed = delay_params.get("seed")
            hex_pi = delay_params.get("proof")
            seed = funcs.hex2int(hex_seed)
            pi = funcs.hex2int(hex_pi)
            Calculator().update(seed, pi)

    def notify_insert(self):
        if self.__insert_lock.locked():
            logging.debug("Insert locked.")
            return

        with self.__insert_lock:
            Selector().insert_block()
            self.__await_block_count = 0

    def append_block(self, block):
        """
        向队列中添加区块，这部分区块要等待选择器选择后再插入
        """
        block_hash = block.hash

        if block_hash in self.__known_block:
            return

        with self.__append_lock:
            if block_hash in self.__known_block:
                return
            self.__queued_block.put(block)
            self.__known_block[block_hash] = block
            self.__await_block_count += 1
            logging.debug("Append block #{} to manager.".format(block_hash))
            with self.__cond:
                self.__cond.notify_all()

    def get_known_block(self, block_hash):
        return self.__known_block[block_hash]

    def is_known_block(self, block_hash):
        return block_hash in self.__known_block

    @property
    def await_block(self):
        return self.__await_block_count

    def __broadcast(self, block):
        """
        广播新区块， 选取 sqrt(n) 个邻居发送区块，其他的邻居只发送哈希值
        待优化
        """
        clients = Peer(Manager()).clients
        count = len(clients)
        block_hash = block.hash

        broadcast_block_count = int(sqrt(count))
        broadcast_block_clients = random.sample(clients, broadcast_block_count)

        for client in broadcast_block_clients:
            client.append_block_queue(block)

        for client in clients:
            if client in broadcast_block_clients:
                continue
            client.append_hash_queue(block_hash)