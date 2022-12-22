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
        # 交易打包队列
        self.tx_queue = Queue()
        # 上一次打包的队列，如果区块打包失败，tx不会在dict中被清除
        self.prev_queue = Queue()
        self.bc = BlockChain()
        # todo: 存在潜在的类型转换错误，如果config文件配置错误可能抛出错误
        self.SIZE = int(Config().get("node.mem_pool_size"))

        self.__queue_set = set()
        self.__height = -1
        self.__status = TxMemPool.STATUS_NONE
        self.pool_lock = threading.Lock()
        self.__read_lock = threading.Lock()
        self.__cond = threading.Condition()

    def is_full(self):
        return len(self.txs) >= self.SIZE

    def add(self,
            tx) -> None:
        """ 将一笔交易放入交易池中

        在本地节点正在打包时会进行等待
        首先在集合中放入交易的哈希，然后再放入交易到字典中
        最后，把交易的哈希值放入到打包队列中等待

        Args:
            tx: 待放入的交易
        Returns:
            如果成功放入交易返回 True
        """
        with self.__cond:
            while self.__read_lock.locked():
                logging.debug("Node packaging block, stay wait.")
                self.__cond.wait()

        tx_hash = tx.tx_hash
        # 在添加交易到交易池前先检查交易是否存在，如果存在说明已经被打包了
        with self.pool_lock:
            self.__status = TxMemPool.STATUS_APPEND

            if tx_hash not in self.__queue_set and tx_hash not in self.txs:
                self.__queue_set.add(tx_hash)
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
        self.pool_lock.release()

    def package(self,
                height) -> list | None:
        """ 打包交易

        需要传入当前的高度， 通过高度限制交易池的打包
        回滚的情况下会直接修改交易池的高度，这里的逻辑可能会引起错误，需要后续观察
          - 首先从 prev 队列中取出交易，该队列存储了上一次打包的交易，为了避免由于回退导致交易丢失，每次打包会将这一次打包队列中的交易
            移动到 prev 队列中
          - 然后处理打包队列中的交易，将他们提出并且哈希值放入 prev 队列

        Args:
            height: 目前的区块高度
        Returns:
            返回一个打包好的交易列表，如果打包失败或者该高度下已经打包返回None
        """
        result = []
        bc = BlockChain()
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

                while count < pool_size and not self.prev_queue.empty():
                    logging.debug("Pop transaction from prev queue.")

                    if self.prev_queue.empty():
                        logging.debug("Memory pool cleaned.")
                        break
                    tx_hash = self.prev_queue.get()
                    self.__queue_set.remove(tx_hash)

                    if tx_hash not in self.txs:
                        continue

                    transaction = self.txs[tx_hash]

                    # if not bc.verify_transaction(transaction):
                    #     continue

                    result.append(transaction)
                    count += 1

                while count < pool_size and not self.tx_queue.empty():
                    logging.debug("Pop transaction from pool.")

                    if self.tx_queue.empty():
                        logging.debug("Memory pool cleaned.")
                        break

                    tx_hash = self.tx_queue.get()

                    if tx_hash not in self.txs:
                        continue

                    transaction = self.txs[tx_hash]
                    # db_tx = bc.get_transaction_by_tx_hash(tx_hash)

                    # if not bc.verify_transaction(transaction):
                    #     continue

                    self.prev_queue.put(tx_hash)
                    result.append(transaction)
                    count += 1

                with self.__cond:
                    self.__cond.notify_all()
        self.__status = TxMemPool.STATUS_NONE
        logging.debug("Package {} transactions.".format(len(result)))

        return result

    def set_height(self,
                   height,
                   is_rollback=False) -> None:
        """ 设置交易池高度

        只有在回退或是高度大于交易池高度的情况下才能回滚
        Args:
            height: 待设置高度
            is_rollback: 是否回滚的处理逻辑
        Returns: None
        """
        if not is_rollback and height <= self.__height:
            return

        if is_rollback:
            logging.debug("Rollback, set pool height to #{}.".format(height))
        self.__height = height

    def remove(self, tx_hash) -> None:
        """ 从交易池移出交易
        Args:
            tx_hash: 待移除的交易的哈希值
        Returns: None
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
