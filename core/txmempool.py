from core.config import Config
from utils.singleton import Singleton


class TxMemPool(Singleton):
    def __init__(self):
        self.txs = {}
        self.tx_hashes = []
        # todo: 存在潜在的类型转换错误，如果config文件配置错误可能抛出错误
        self.SIZE = int(Config().get("node.mem_pool_size"))

    def is_full(self):
        return len(self.txs) >= self.SIZE

    def add(self, tx):
        tx_hash = tx.tx_hash
        if tx_hash not in self.txs.keys():
            self.txs[tx_hash] = tx
            self.tx_hashes.append(tx_hash)

    def clear(self):
        self.txs.clear()
        self.tx_hashes.clear()

    def package(self):
        tx_hash = self.tx_hashes.pop()
        result = self.txs.pop(tx_hash)
        return result

    def remove(self, tx_hash):
        """
        从交易吃池移出交易
        :param tx_hash:
        :return:
        """
        if tx_hash in self.tx_hashes:
            self.tx_hashes.remove(tx_hash)
            self.txs.pop(tx_hash)
