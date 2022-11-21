import unittest

from utils.leveldb import LevelDB
from core.block_chain import BlockChain
from core.utxo import UTXOSet


class TestUTxO(unittest.TestCase):

    def test_utxo_reindex(self):
        bc = BlockChain()
        UTXOSet().reindex(bc)

        block, block_hash = bc.get_latest_block()
        self.assertEqual(UTXOSet().get_latest_height(), block.height)

    def test_find_utxo(self):
        utxos = UTXOSet().find_utxo("1PuRN6PvTfhVazxoK8zZ3eFvTUSU76VHRF")
        print(utxos)