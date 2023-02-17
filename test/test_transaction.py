import hashlib
import time
import unittest
import ecdsa
import binascii

from core.transaction import Transaction

class TestTransaction(unittest.TestCase):
    def test_verify(self):
        prv = "9beb4bdbe87c931b0517877819384b79847c2918ba575fa495f907aed4d77d0a"
        sign_key = ecdsa.SigningKey.from_string(binascii.a2b_hex(prv), curve=ecdsa.SECP256k1)

        tx_data = hashlib.sha384(str(time.time()).encode()).hexdigest()
        raw_transaction = Transaction(tx_data)
        raw_transaction.set_tx_hash(sign_key)

        self.assertTrue(raw_transaction.verify())