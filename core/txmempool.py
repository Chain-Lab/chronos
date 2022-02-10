from utils.singleton import Singleton
from core.config import Config


class TxMemPool(Singleton):
    def __init__(self):
        self.txs = []
        # todo: 存在潜在的类型转换错误，如果config文件配置错误可能抛出错误
        self.SIZE = int(Config().get("node.mem_pool_size"))

    def is_full(self):
        return len(self.txs) >= self.SIZE

    def add(self, tx):
        self.txs.append(tx)

    def clear(self):
        self.txs.clear()

    def package(self):
        result = self.txs[0]
        del self.txs[0]
        return result
