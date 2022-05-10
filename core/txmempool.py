import logging
import threading
from queue import Queue

from core.block_chain import BlockChain
from core.config import Config
from utils.singleton import Singleton


class TxMemPool(Singleton):
    STATUS_NONE = 0
    STATUS_APPEND = 1
    STATUS_PACKAGE = 2

    def __init__(self):
        self.txs = {}
        self.tx_queue = Queue()
        self.bc = BlockChain()
        # todo: 存在潜在的类型转换错误，如果config文件配置错误可能抛出错误
        self.SIZE = int(Config().get("node.mem_pool_size"))
        self.__height = -1
        self.__status = TxMemPool.STATUS_NONE
        self.pool_lock = threading.Lock()
        self.__read_lock = threading.Lock()
        self.__cond = threading.Condition()

    def is_full(self):
        return len(self.txs) >= self.SIZE

    def add(self, tx):

        with self.__cond:
            while self.__read_lock.locked():
                logging.debug("Node packaging block, stay wait.")
                self.__cond.wait()

        tx_hash = tx.tx_hash
        # 在添加交易到交易池前先检查交易是否存在，如果存在说明已经被打包了
        with self.pool_lock:
            self.__status = TxMemPool.STATUS_APPEND
            if self.bc.get_transaction_by_tx_hash(tx_hash) is not None:
                logging.debug("Transaction #{} existed.".format(tx_hash))
                self.__status = TxMemPool.STATUS_NONE
                return False
            if tx_hash not in self.txs:
                self.txs[tx_hash] = tx
                # self.tx_hashes.append(tx_hash)
                self.tx_queue.put(tx_hash)
                logging.debug("Add tx#{} in memory pool.".format(tx_hash))
                self.__status = TxMemPool.STATUS_NONE
                return True
            self.__status = TxMemPool.STATUS_NONE
            return False

    def clear(self):
        self.pool_lock.acquire()
        self.txs.clear()
        # self.tx_hashes.clear()
        self.pool_lock.release()

    def package(self, height):
        """
        :params height: 即将打包的区块的高度， 如果小于已打包高度说明已经被打包过
        :return: 高度高于已打包高度的情况下返回交易列表， 否则返回None
        """
        result = []
        bc = BlockChain()
        # logging.debug("Package pool, pool status:")
        # logging.debug(self.tx_hashes)
        if height <= self.__height or self.__read_lock.locked():
            logging.debug("Mempool height #{}, package height #{}.".format(self.__height, height))
            return None

        with self.__read_lock:
            with self.pool_lock:
                self.__status = TxMemPool.STATUS_PACKAGE
                logging.debug("Lock txmempool.")
                # 拿到锁后再检查一次， 避免某个线程刚好到达这个地方抢到锁
                if height <= self.__height:
                    logging.debug("Height#{} < mempool height #{}.".format(height, self.__height))
                    self.pool_lock.release()
                    logging.debug("Release txmempool lock.")
                    self.__status = TxMemPool.STATUS_NONE
                    with self.__cond:
                        self.__cond.notify_all()
                    return None
                logging.debug("Memory pool height #{}, set height #{}".format(self.__height, height))
                self.__height = height
                pool_size = int(Config().get("node.mem_pool_size"))
                count = 0
                tx_hashes = Queue()

                while count < pool_size and not self.tx_queue.empty():
                    logging.debug("Pop transaction from pool.")

                    if self.tx_queue.empty():
                        logging.debug("Memory pool cleaned.")
                        break

                    tx_hash = self.tx_queue.get()

                    if tx_hash not in self.txs:
                        continue

                    tx_hashes.put(tx_hash)
                    transaction = self.txs.pop(tx_hash)
                    db_tx = bc.get_transaction_by_tx_hash(tx_hash)

                    if db_tx is not None:
                        continue

                    if not bc.verify_transaction(transaction):
                        continue

                    result.append(transaction)
                    count += 1

                while not tx_hashes.empty():
                    self.tx_queue.put(tx_hashes.get())

                with self.__cond:
                    self.__cond.notify_all()
        self.__status = TxMemPool.STATUS_NONE
        logging.debug("Package {} transactions.".format(len(result)))

        return result

    def rollback_height(self, height):
        logging.debug("Txmempool roll back to height #{}.".format(height))
        self.__height = height

    def remove(self, tx_hash):
        """
        从交易池移出交易
        :param tx_hash:
        :return:
        """
        self.pool_lock.acquire()
        if tx_hash in self.txs:
            self.txs.pop(tx_hash)
            logging.debug("Remove tx#{} from memory pool.".format(tx_hash))
        self.pool_lock.release()

    @property
    def height(self):
        return self.__height

    @property
    def counts(self):
        return self.tx_queue.qsize()

    @property
    def valid_txs(self):
        return len(self.txs)
