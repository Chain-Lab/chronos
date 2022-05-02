import logging
import threading
import time

from core.block_chain import BlockChain
from core.utxo import UTXOSet
from threads.calculator import Calculator
from threads.counter import Counter
from threads.vote_center import VoteCenter
from utils import funcs
from utils.singleton import Singleton
from node.timer import Timer


class MergeThread(Singleton):
    """
    区块合并的单例线程, Client/Server向该线程发送区块
    该线程专门处理区块信息， 保证在链上只有一条主链
    """

    STATUS_APPEND = 0                        # 区块成功添加到队列
    STATUS_LOCKED = 1                        # 队列被锁
    STATUS_EXISTS = 2                        # 区块已经存在

    def __init__(self):
        """
        线程实例初始化， 在调用MergeThread()时先初始化才添加区块
        """
        """
        cache的结构:
        {
            hash(string): status(bool)
            表示哈希值对应的区块是否被线程处理过
        }
        """
        self.cache = {}

        self.__queue = []
        self.__cond = threading.Condition()
        self.__lock = threading.Lock()
        self.thread = threading.Thread(target=self.__task, args=(), name="Merge Thead")
        self.thread.start()
        self.__cleaner = threading.Thread(target=self.__clear_task, args=(), name="Cleaner Thread")
        self.__cleaner.start()

    def append_block(self, block):
        """
        将区块添加到队列中， 添加之前检查一下在cache中是否存在
        :param block: 从邻居节点接收到的区块
        :return: None
        """
        block_hash = block.header_hash

        bc = BlockChain()
        block_height = block.height
        prev_hash = block.block_header.prev_block_hash

        if prev_hash not in self.cache.keys() and block_height != 0:
            logging.info("Previous block#{} not exists, pull block.".format(prev_hash))
            return MergeThread.STATUS_EXISTS

        self.__lock.acquire()
        if block_hash in self.cache.keys():
            logging.info("Block#{} already in cache.".format(block_hash))
            self.__lock.release()
            if not self.cache[block_hash]:
                return MergeThread.STATUS_EXISTS
            else:
                return MergeThread.STATUS_APPEND
        with self.__cond:
            logging.info("Append Block#{} height {} to queue.".format(block_hash, block_height))
            self.__queue.append(block)
            self.__cond.notify_all()
        self.__lock.release()
        return MergeThread.STATUS_APPEND

    def __update(self, block):
        height = block.block_header.height

        VoteCenter().refresh(height)
        Counter().refresh(height)
        Timer().refresh(height)

        delay_params = block.transactions[0].inputs[0].delay_params
        hex_seed = delay_params.get("seed")
        hex_pi = delay_params.get("proof")
        seed = funcs.hex2int(hex_seed)
        pi = funcs.hex2int(hex_pi)
        Calculator().update(seed, pi)

    def __task(self):
        """
        区块信息处理线程的线程函数
        在队列中存在区块的时候进行处理
        @return:
        """
        bc = BlockChain()

        while True:
            with self.__cond:
                while not len(self.__queue):
                    self.__cond.wait()
                block = self.__queue.pop()

                block_height = block.block_header.height
                block_hash = block.block_header.hash
                block_prev_hash = block.block_header.prev_block_hash
                logging.debug("Pop block#{} from queue.".format(block_hash))
                latest_block, latest_hash = bc.get_latest_block()

                if not latest_block:
                    logging.info("Insert genesis block to database.")
                    bc.insert_block(block)
                    self.__update(block)
                    continue

                latest_height = latest_block.block_header.height
                self.cache[block_hash] = True

                logging.debug("Latest block: {}".format(latest_block))
                logging.debug("Now block: {}".format(block))

                # 获取到的该区块的高度低于或等于本地高度， 说明区块已经存在
                if block_height <= latest_height:
                    logging.info("Block has equal block, check whether block is legal.")
                    block_count = block.vote_count
                    block_timestamp = block.block_header.timestamp

                    # 获取到本地存储的对等高度的区块
                    equal_block = bc.get_block_by_height(block_height)
                    equal_count = equal_block.vote_count
                    equal_hash = equal_block.block_header.hash
                    equal_timestamp = block.block_header.timestamp
                    equal_prev_hash = equal_block.block_header.prev_block_hash
                    # 比较的大前提是两个区块的前一个区块一致（分叉点）， 并且区块哈希值不一样
                    if block_hash == equal_hash or block_prev_hash != equal_prev_hash or block_count < equal_count or (
                            block_count == equal_count and block_timestamp > equal_timestamp):
                        logging.info("block#{} < equal block.".format(block_hash))
                        continue

                    # 如果代码逻辑到达这里， 说明需要进行区块的回退
                    rollback_times = latest_height - block_height + 1
                    for _ in range(rollback_times):
                        latest_block, _ = bc.get_latest_block()
                        logging.info("Rollback block#{}.".format(latest_block.block_header.hash))
                        UTXOSet().roll_back(latest_block)
                        bc.roll_back()
                    bc.insert_block(block)
                    self.__update(block)
                    continue
                elif block_height == latest_height + 1:
                    # 取得区块的前一个区块哈希
                    block_prev_hash = block.block_header.prev_block_hash
                    if block_prev_hash == latest_hash:
                        bc.insert_block(block)
                        self.__update(block)
                    else:
                        # 最前面的区块没有被处理过， 将区块返回到队列中等待
                        if block_prev_hash in self.cache.keys() and not self.cache[block_prev_hash]:
                            logging.debug("Block#{} push back to queue.".format(block_hash))
                            self.__queue.append(block)
                            self.cache[block_hash] = False

    def __clear_task(self):
        while True:
            time.sleep(180)
            with self.__lock:
                self.cache.clear()
