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

    def is_full(self):
        return len(self.txs) >= self.SIZE

    def add(self, tx):
        tx_hash = tx.tx_hash
        # 在添加交易到交易池前先检查交易是否存在，如果存在说明已经被打包了
        if self.bc.get_transaction_by_tx_hash(tx_hash) is not None:
            return
        if tx_hash not in self.tx_hashes:
            self.txs[tx_hash] = tx
            self.tx_hashes.append(tx_hash)
            logging.debug("Add tx#{} in memory pool.".format(tx_hash))

    def clear(self):
        self.pool_lock.acquire()
        self.txs.clear()
        self.tx_hashes.clear()
        self.pool_lock.release()

    def package(self):
        logging.debug("Package pool, pool status:")
        logging.debug(self.tx_hashes)
        if self.pool_lock.locked() or len(self.tx_hashes) == 0:
            return None

        self.pool_lock.acquire()
        tx_hash = self.tx_hashes.pop()
        result = self.txs.pop(tx_hash)
        logging.debug(self.tx_hashes)
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
