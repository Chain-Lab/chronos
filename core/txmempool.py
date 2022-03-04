from core.config import Config
from utils.singleton import Singleton


class TxMemPool(Singleton):
    def __init__(self):
        self.txs = []
        self.tx_hashes = []
        # todo: 存在潜在的类型转换错误，如果config文件配置错误可能抛出错误
        self.SIZE = int(Config().get("node.mem_pool_size"))

    def is_full(self):
        return len(self.txs) >= self.SIZE

    def add(self, tx):
        if tx.tx_hash not in self.tx_hashes:
            self.tx_hashes.append(tx.tx_hash)
            self.txs.append(tx)

    def clear(self):
        self.txs.clear()
        self.tx_hashes.clear()

    def package(self):
        result = self.txs[0]
        del self.txs[0]
        return result
