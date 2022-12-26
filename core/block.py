import logging

from core.block_header import BlockHeader
from core.config import Config
from core.transaction import Transaction


class Block(object):

    def __init__(self, block_header=None, transactions=None):
        self._block_header = block_header
        self._transactions = transactions
        self._magic_no = Config().get('node.magic_no')

    def set_header_hash(self, prev_block_hash=None) -> None:
        self._block_header.set_hash(prev_block_hash)

    def set_transaction(self, txs):
        self._transactions = txs

    def set_hash_merkle_tree(self, hash_merkle_root):
        self._block_header.hash_merkle_root = hash_merkle_root

    @classmethod
    def new_genesis_block(cls, coinbase_tx):
        block_header = BlockHeader.new_genesis_block_header()
        return cls(block_header, coinbase_tx)

    @property
    def vote_info(self):
        return self._transactions[0].inputs[0].vote_info

    @property
    def vote_count(self) -> int:
        """ 统计该区块记录的投票信息

        Coinbase 交易下存储了该区块生成时的投票信息
        该函数取出区块的 Coinbase 交易，然后遍历统计投票数据

        Returns:
            返回一个整数，表示当前区块下的投票地址数量
        """
        return 0
        # vote_info: dict
        # vote_info = self.vote_info
        # result = 0
        # logging.debug("BLock#{} vote info data: {}".format(self.block_header.hash, vote_info))
        # logging.debug("Block data: {}".format(self.serialize()))
        # for item in vote_info.values():
        #     result += len(item)
        # return result

    def delay_params(self):
        return self._transactions[0].inputs[0].delay_params

    @property
    def block_header(self):
        return self._block_header

    @property
    def transactions(self):
        return self._transactions

    @property
    def header_hash(self):
        return self._block_header.hash

    @property
    def height(self):
        return self._block_header.height

    def __repr__(self):
        return "Block(block_header=%s)" % self._block_header

    def __eq__(self, other):
        if not isinstance(other, Block):
            return False
        return self.block_header.hash == other.block_header.hash

    def serialize(self):
        return {
            "magic_no": self._magic_no,
            "block_header": self._block_header.serialize(),
            "transactions": [tx.serialize() for tx in self._transactions]
        }

    @classmethod
    def deserialize(cls, data: dict):
        block_header_dict = data['block_header']
        block_header = BlockHeader()
        block_header.deserialize(block_header_dict)
        transactions = data['transactions']
        txs = []
        for transaction in transactions:
            txs.append(Transaction.deserialize(transaction))
        return cls(block_header, txs)
