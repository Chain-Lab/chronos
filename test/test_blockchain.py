import binascii
import unittest

from core.transaction import Transaction
from utils.leveldb import LevelDB
from core.utxo import UTXOSet
from core.txmempool import TxMemPool
from core.block_chain import BlockChain
from utils import number_theory
from utils import funcs


class TestBlockchain(unittest.TestCase):

    def test_1_genesis(self):
        p = number_theory.get_prime(512)
        q = number_theory.get_prime(512)
        n = p * q
        t = 10000000

        delay_params = {
            "order": binascii.b2a_hex(n.to_bytes(
                length=(n.bit_length() + 7) // 8,
                byteorder='big',
                signed=False
            )).decode(),
            "time_param": t,
            # 在目前开发过程中设置为默认的256位随机数
            "seed": funcs.int2hex(number_theory.get_prime(256)),
            # 用于验证的参数， 节点计算的同时计算proof
            "verify_param": funcs.int2hex(number_theory.get_prime(256))
        }

        bc = BlockChain()
        tx = Transaction.coinbase_tx({}, delay_params)
        bc.new_genesis_block(tx)

        block = bc.get_block_by_height(0)

        self.assertNotEqual(None, block)

        self.assertEqual(block.block_header.height, 0)

    def test_2_insert_block(self):
        bc = BlockChain()
        new_block = bc.package_new_block([], {}, {})

        self.assertNotEqual(new_block, None)
        bc.insert_block(new_block)
        block, block_hash = bc.get_latest_block()

        self.assertEqual(block.height, new_block.height)

    def test_2_get_transaction(self):
        bc = BlockChain()
        block = bc[0]
        tx = block.transactions[0]

        db_tx = bc.get_transaction_by_tx_hash(tx.tx_hash)

        self.assertNotEqual(db_tx, None)
        self.assertEqual(db_tx.tx_hash, tx.tx_hash)

    def test_2_find_utxos(self):
        bc = BlockChain()
        bc.find_utxo()

    def test_2_package_with_transaction(self):
        pass

    def test_3_roll_back(self):
        bc = BlockChain()
        block, latest_hash = bc.get_latest_block()
        height = block.height

        UTXOSet().roll_back(block, bc)
        bc.roll_back()
        block, latest_hash = bc.get_latest_block()
        self.assertEqual(height - 1, block.height)