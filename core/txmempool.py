import logging
import threading

from core.config import Config
from core.block_chain import BlockChain
from utils.singleton import Singleton


class TxMemPool(Singleton):
    def __init__(self):
        self.txs = {}
        self.tx_hashes = []
        self.pool_lock = threading.Lock()
        self.bc = BlockChain()
        # todo: 存在潜在的类型转换错误，如果config文件配置错误可能抛出错误
        self.SIZE = int(Config().get("node.mem_pool_size"))
        self.__height = -1

    def is_full(self):
        return len(self.txs) >= self.SIZE

    def add(self, tx):
        tx_hash = tx.tx_hash
        # 在添加交易到交易池前先检查交易是否存在，如果存在说明已经被打包了
        if self.bc.get_transaction_by_tx_hash(tx_hash) is not None:
            logging.debug("Transaction #{} existed.".format(tx_hash))
            return False
        if tx_hash not in self.tx_hashes:
            self.txs[tx_hash] = tx
            self.tx_hashes.append(tx_hash)
            logging.debug("Add tx#{} in memory pool.".format(tx_hash))
            return True
        return False

    def clear(self):
        self.pool_lock.acquire()
        self.txs.clear()
        self.tx_hashes.clear()
        self.pool_lock.release()

    def package(self, height):
        """
        :params height: 即将打包的区块的高度， 如果小于已打包高度说明已经被打包过
        :return: 高度高于已打包高度的情况下返回交易列表， 否则返回None
        """
        result = []
        logging.debug("Package pool, pool status:")
        logging.debug(self.tx_hashes)
        if height <= self.__height or self.pool_lock.locked():
            return None

        self.pool_lock.acquire()
        # 拿到锁后再检查一次， 避免某个线程刚好到达这个地方抢到锁
        if height <= self.__height:
            self.pool_lock.release()
            return None
        self.__height = height
        pool_size = int(Config().get("node.mem_pool_size"))
        count = 0
        length = len(self.tx_hashes)

        while count < pool_size and count < length:
            tx_hash = self.tx_hashes.pop()
            transaction = self.txs.pop(tx_hash)
            result.append(transaction)
            count += 1

        self.pool_lock.release()
        return result

    def remove(self, tx_hash):
        """
        从交易池移出交易
        :param tx_hash:
        :return:
        """
        self.pool_lock.acquire()
        if tx_hash in self.tx_hashes:
            self.tx_hashes.remove(tx_hash)
            self.txs.pop(tx_hash)
        self.pool_lock.release()
