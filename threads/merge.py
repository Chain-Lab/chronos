import logging
import threading

from core.block_chain import BlockChain
from core.utxo import UTXOSet
from utils.singleton import Singleton


class MergeThread(Singleton):
    """
    区块合并的单例线程, Client/Server向该线程发送区块
    该线程专门处理区块信息， 保证在链上只有一条主链
    """

    def __init__(self):
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
        self.thread = None

    def append_block(self, block):
        """
        将区块添加到队列中， 添加之前检查一下在cache中是否存在
        :param block: 从邻居节点接收到的区块
        :return: None
        """
        block_hash = block.header_hash
        if block_hash in self.cache.keys() or self.__lock.locked():
            logging.info("Block#{} already in cache.".format(block_hash))
            return True

        self.__lock.acquire()
        with self.__cond:
            self.__queue.append(block)
            self.__cond.notify_all()
        self.__lock.release()
        return True

    def run(self):
        self.thread = threading.Thread(target=self.__task, args=())
        self.thread.start()

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
                logging.debug("Pop block#{} from queue.".format(block_hash))
                latest_block, latest_hash = bc.get_latest_block()

                if not latest_block:
                    logging.info("Insert genesis block to database.")
                    bc.insert_block(block)
                    continue

                latest_height = latest_block.block_header.height
                self.cache[block_hash] = True

                logging.debug("Latest block: {}".format(latest_block))

                # 获取到的该区块的高度低于或等于本地高度， 说明区块已经存在
                if block_height <= latest_height:
                    logging.info("Block has equal block, check whether legal.")
                    block_count = block.vote_count
                    block_timestamp = block.block_header.timestamp

                    # 获取到本地存储的对等高度的区块
                    equal_block = bc.get_block_by_height(block_height)
                    equal_count = equal_block.vote_count
                    equal_hash = equal_block.block_header.hash
                    equal_timestamp = block.block_header.timestamp
                    if block_hash == equal_hash or block_count < equal_count or (
                            block_count == equal_count and block_timestamp > equal_timestamp):
                        continue

                    # 如果代码逻辑到达这里， 说明需要进行区块的回退
                    rollback_times = latest_height - block_height
                    for _ in range(rollback_times):
                        latest_block, _ = bc.get_latest_block()
                        logging.info("Rollback block#{}.".format(latest_block.block_header.hash))
                        UTXOSet().roll_back(latest_block)
                        bc.roll_back()
                    bc.insert_block(block)
                    continue
                elif block_height == latest_height + 1:
                    # 取得区块的前一个区块哈希
                    block_prev_hash = block.block_header.prev_block_hash
                    if block_prev_hash == latest_hash:
                        bc.insert_block(block)
                    else:
                        # 最前面的区块没有被处理过， 将区块返回到队列中等待
                        if block_prev_hash not in self.cache.keys() or not self.cache[block_prev_hash]:
                            logging.debug("Block#{} push back to queue.".format(block_hash))
                            self.__queue.append(block)
                            self.cache[block_hash] = False
