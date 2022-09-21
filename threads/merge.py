import logging
import threading
import time

from lru import LRU

from core.block_chain import BlockChain
from core.txmempool import TxMemPool
from core.utxo import UTXOSet
from node.timer import Timer
from threads.calculator import Calculator
from threads.counter import Counter
from threads.vote_center import VoteCenter
from utils import funcs
from utils.singleton import Singleton
from queue import Queue

from utils import constant


class MergeThread(Singleton):
    """
    区块合并的单例线程, Client/Server向该线程发送区块
    该线程专门处理区块信息， 保证在链上只有一条主链
    """

    STATUS_APPEND = 0  # 区块成功添加到队列
    STATUS_LOCKED = 1  # 队列被锁
    STATUS_EXISTS = 2  # 区块已经存在
    STATUS_PULL   = 3

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
        # todo: 放入到配置中
        # self.cache = LRU(500)
        self.cache = {}

        self.__queue = Queue()
        self.__cond = threading.Condition()
        self.__lock = threading.Lock()
        self.thread = threading.Thread(target=self.__task, args=(), name="Merge Thread")
        self.thread.start()
        # self.__cleaner = threading.Thread(target=self.__clear_task, args=(), name="Cleaner Thread")
        # self.__cleaner.start()

    def append_block(self, block):
        """
        将区块添加到队列中， 添加之前检查一下在cache中是否存在
        :param block: 从邻居节点接收到的区块
        :return: None
        """
        block_hash = block.header_hash

        bc = BlockChain()
        # latest_block, _ = bc.get_latest_block()
        # if latest_block is not None:
        #     latest_height = latest_block.block_header.height
        # else:
        #     latest_height = 0
        block_height = block.height
        prev_hash = block.block_header.prev_block_hash
        prev_block = bc.get_block_by_hash(prev_hash)
        # delta = abs(latest_height - block_height)

        # 如果前一个区块在本地没有出现过， 拉取前一股区块
        if prev_hash not in self.cache and block_height != 0 and prev_block is None:
            # and delta < 5:
            logging.info("Previous block#{} not exists, pull block.".format(prev_hash))
            return MergeThread.STATUS_PULL

        self.__lock.acquire()
        # 如果该区块在本地出现过
        if block_hash in self.cache:
            logging.info("Block#{} already in cache.".format(block_hash))
            self.__lock.release()
            # 如果cache[hash]是false并且前一个区块不存在（prev_block=None）
            if not self.cache[block_hash]['status']:
                # 区块没有被处理过且前一个区块不在数据库
                # 返回区块已经存在
                return MergeThread.STATUS_EXISTS if prev_block else MergeThread.STATUS_PULL
            else:
                # 区块被处理过或者前一个区块在数据库中
                return MergeThread.STATUS_APPEND

        # 如果该区块在本地没有出现过（不在cache中也没有在数据库中）
        with self.__cond:
            logging.info("Append Block#{} height {} to queue.".format(block_hash, block_height))
            self.__queue.put(block)
            self.cache[block_hash] = {
                'status': False,
                'prev_hash': prev_hash
            }
            self.__cond.notify_all()
        self.__lock.release()
        return MergeThread.STATUS_APPEND

    @staticmethod
    def __update(block, rolled_back=False):
        height = block.block_header.height
        logging.debug("Update votecenter, calculator, mempool with height #{} rollback: {}".format(height, rolled_back))

        # 注意更新顺序
        VoteCenter().refresh(height, rolled_back)
        Counter().refresh(height, rolled_back)
        Timer().refresh()

        delay_params = block.transactions[0].inputs[0].delay_params
        hex_seed = delay_params.get("seed")
        hex_pi = delay_params.get("proof")
        seed = funcs.hex2int(hex_seed)
        pi = funcs.hex2int(hex_pi)
        Calculator().update(seed, pi)

        tx_mem_pool = TxMemPool()
        tx_mem_pool.set_height(height, rolled_back)
        for tx in block.transactions:
            tx_hash = tx.tx_hash
            tx_mem_pool.remove(tx_hash)

    def __task(self):
        """
        区块信息处理线程的线程函数
        在队列中存在区块的时候进行处理
        @return:
        """
        bc = BlockChain()

        while True:
            if not constant.NODE_RUNNING:
                logging.debug("Receive stop signal, stop thread.")
                break

            with self.__cond:
                while self.__queue.empty():
                    self.__cond.wait()
                block = self.__queue.get()

                block_height = block.block_header.height
                block_hash = block.block_header.hash
                block_prev_hash = block.block_header.prev_block_hash
                logging.debug("Pop block#{} from queue.".format(block_hash))
                latest_block, latest_hash = bc.get_latest_block()

                # 最新区块不存在， 直接添加到数据库
                if not latest_block:
                    # 如果不存在最新区块， 直接insert
                    logging.info("Insert genesis block to database.")
                    self.__update(block)
                    bc.insert_block(block)
                    continue

                latest_height = latest_block.block_header.height
                self.cache[block_hash]['status'] = True

                logging.debug("Latest block: {}".format(latest_block))
                logging.debug("Now block: {}".format(block))

                # 获取到的该区块的高度低于或等于本地高度， 说明区块已经存在
                if block_height <= latest_height:
                    logging.info("Block has equal block, check whether block is legal.")
                    block_count = block.vote_count
                    block_timestamp = block.block_header.timestamp

                    # 获取到本地存储的对等高度的区块, 以及用于比较的信息
                    equal_block = bc.get_block_by_height(block_height)
                    equal_count = equal_block.vote_count
                    equal_hash = equal_block.block_header.hash
                    equal_timestamp = equal_block.block_header.timestamp
                    equal_prev_hash = equal_block.block_header.prev_block_hash

                    # 比较的大前提是两个区块的前一个区块一致（分叉点）， 并且区块哈希值不一样
                    logging.debug(
                        "Block vote count is {}. Equal block vote count is {}.".format(block_count, equal_count))
                    logging.debug(
                        "Block timestamp is {}. Equal block timestamp is {}.".format(block_timestamp, equal_timestamp))

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

                    # 回退然后更新, 回退后需要保证投票中心的更新
                    self.__update(block, True)
                    bc.insert_block(block)
                    continue
                elif block_height == latest_height + 1:
                    # 取得区块的前一个区块哈希
                    block_prev_hash = block.block_header.prev_block_hash
                    if block_prev_hash == latest_hash:
                        # 在需要insert时优先更新同步使用的信息
                        self.__update(block)
                        bc.insert_block(block)
                    else:
                        # 最前面的区块没有被处理过， 将区块返回到队列中等待
                        # 追溯到最前面的区块， 并且检查是否被处理过， 需要在cache中存储前一个区块的信息
                        front_block_hash = self.__scan_prev_blocks(block_hash)
                        if self.cache[front_block_hash]['status']:
                            logging.debug("Block is not main chain block.")
                        else:
                            logging.debug("Push block#{} back to queue.".format(block_hash))
                            self.__queue.put(block)
                            self.cache[block_hash]['status'] = False
                else:
                    # 如果区块的高度高于目前区块一个区块以上， 返回到队列中等待处理
                    if block_prev_hash in self.cache.keys() and not self.cache[block_prev_hash]:
                        logging.debug("Block#{} push back to queue.".format(block_hash))
                        self.__queue.put(block)
                        self.cache[block_hash] = False

    def __scan_prev_blocks(self, block_hash):
        '''
        查找一个区块在cache中的最前面的区块
        @param block_hash: 带查找的区块的哈希值
        @return: 最前面的区块的哈希值
        '''
        result = block_hash
        prev_hash = self.cache[block_hash]['prev_hash']
        while prev_hash in self.cache:
            result = prev_hash
            prev_hash = self.cache[result]['prev_hash']
        return result

    def __clear_task(self):
        while True:
            time.sleep(120)
            with self.__lock:
                self.cache.clear()
