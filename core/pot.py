import logging
import time

from core.block_chain import BlockChain
from core.config import Config
from utils import funcs
from utils.b58code import Base58Code
from utils.dbutil import DBUtil


class ProofOfTime(object):
    def __init__(self):
        db_url = Config().get('database.url')
        self.db = DBUtil(db_url)

    def local_vote(self):
        local_address = Config().get('node.address')
        bc = BlockChain()
        delay_params = bc.get_latest_delay_params()
        seed = delay_params.get("seed")
        # 需要处理异常
        seed = funcs.hex2int(seed)
        address_number = int.from_bytes(Base58Code.decode_check(local_address), byteorder='big')
        node_hash = seed * address_number % 2 ** 256
        # 实验测试使用， 在每段时间内有一半的节点会被选为共识节点
        if node_hash / 2 ** 256 > 1.0:
            logging.debug("Local is not consensus node.")
            return None

        local_time = time.time()

        final_address = None
        final_time = 0
        abs_time = 1000

        wallets = self.db.get('wallets', '')

        for item in wallets.items():
            if '_id' in item or '_rev' in item or "" in item:
                continue

            item_address = item[0]
            if item_address == local_address:
                continue

            # 根据vdf的值和钱包地址来确定远端节点是否共识节点
            address_number = int.from_bytes(Base58Code.decode_check(item_address), byteorder='big')
            node_hash = seed * address_number % 2 ** 256
            if node_hash / 2 ** 256 > 0.95:
                continue

            item_time = item[1].get('time')

            if abs(item_time - local_time) < abs_time:
                abs_time = abs(item_time - local_time)
                final_time = item_time
                final_address = item_address

        return final_address
