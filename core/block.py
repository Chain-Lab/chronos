from config import Config
from block_header import BlockHeader
from transaction import Transaction


class Block(object):

    def __init__(self, block_header=None, transactions=None):
        self._block_header = block_header
        self._transactions = transactions
        self._magic_no = Config().get('node.magic_no')

    # todo: 待调整, 需要后面确认blockchain的方法

    def mine(self):
        pass

    def validate(self):
        pass

    def set_header_hash(self):
        self._block_header.set_hash()

    def set_transaction(self, txs):
        self._transactions = txs

    def set_hash_merkle_tree(self, hash_merkle_root):
        self._block_header.hash_merkle_root = hash_merkle_root

    @classmethod
    def new_genesis_block(cls, coinbase_tx):
        block_header = BlockHeader.new_genesis_block_header()
        return cls(block_header, coinbase_tx)

    @property
    def block_header(self):
        return self._block_header

    @property
    def transactions(self):
        return self._transactions

    @property
    def header_hash(self):
        return self._block_header.hash

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
        block_header = BlockHeader.deserialize(block_header_dict)
        transactions = data['transactions']
        txs = []
        for transaction in transactions:
            txs.append(Transaction.deserialize(transaction))
        return cls(block_header, txs)
