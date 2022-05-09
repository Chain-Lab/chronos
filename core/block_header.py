import logging
import time

from utils import funcs


class BlockHeader(object):
    def __init__(self, hash_merkle_root='', height=0, prev_block_hash=''):
        # fixed: 转换为整数毫秒级时间戳
        self.timestamp = str(int(time.time() * 1000))
        self.prev_block_hash = prev_block_hash
        self.hash = None
        self.hash_merkle_root = hash_merkle_root
        self.height = height
        self.nonce = None

    def set_hash(self, prev_block_hash=None):
        logging.debug("Set new block hash with prev block#{}".format(prev_block_hash))

        if not prev_block_hash:
            self.prev_block_hash = prev_block_hash
        data_list = [str(self.timestamp),
                     str(self.prev_block_hash),
                     str(self.hash_merkle_root),
                     str(self.height),
                     str(self.nonce)]
        data = ''.join(data_list)
        self.hash = funcs.sum256_hex(data)

    @classmethod
    def new_genesis_block_header(cls):
        return cls()

    def __repr__(self):
        return "Block(timestamp = {} \n\t" \
               "Merkle Root = {} \n\t" \
               "Previous Hash = {} \n\t" \
               "Hash = {} \n\t" \
               "Nonce = {} \n\t" \
               "Height = {} \n\t)".format(self.timestamp,
                                          self.hash_merkle_root,
                                          self.prev_block_hash,
                                          self.hash,
                                          self.nonce,
                                          self.height
                                          )

    def serialize(self):
        return self.__dict__

    def deserialize(self, data: dict):
        self.__dict__.update(data)
