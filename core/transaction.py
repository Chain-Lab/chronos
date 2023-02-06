import binascii
import copy
import logging
import time

# from fastecdsa import keys
import ecdsa
from core.config import Config
from utils import funcs
from utils.b58code import Base58Code


class Transaction(object):
    __VERSION = b'\0'

    def __init__(self, data: bytes):
        self.tx_hash = ''
        self.sender = ''
        self.pub_key = ''
        self.data = data
        self.timestamp = -1
        self.expiration = -1
        self.signature = None
        self.proof_info = None
        self.delay_params = None

    def set_tx_hash(self, sk=None):
        """
        设置交易哈希值, 如果 sk 为空则不设置签名

        Args:
            sk: 发送者的签名私钥
        """
        if not sk:
            self.timestamp = time.time()
            self.expiration = -1
            self.signature = None
            self.tx_hash = funcs.sum256_hex(str(self.__dict__))
            return

        pub_key = sk.get_verifying_key()
        self.pub_key = binascii.b2a_hex(pub_key.to_string()).decode()
        self.sender = funcs.pub_to_address(self.pub_key)
        self.timestamp = time.time()
        self.expiration = self.timestamp + 600

        data = str(self.__dict__)
        self.tx_hash = funcs.sum256_hex(data)

        signature = sk.sign(self.tx_hash.encode())
        self.signature = signature

    def verify(self) -> bool:
        if self.is_coinbase():
            return True

        tx_copy = copy.deepcopy(self)
        tx_copy.signature = None
        tx_hash = funcs.sum256_hex(str(self.__dict__))
        vk = ecdsa.VerifyingKey.from_string(binascii.a2b_hex(tx_copy.pub_key), ecdsa.SECP256k1)

        try:
            if not vk.verify(tx_copy.signature, tx_hash.encode()):
                return False
        except ecdsa.BadSignatureError:
            return False

        return True

    def is_coinbase(self):
        return self.expiration == -1 and not self.signature

    def serialize(self):
        return self.__dict__

    def deserialize(self, data: dict):
        self.__dict__ = data

    def __repr__(self):
        return str(self.__dict__)

    @classmethod
    def coinbase_tx(cls, proof_info: dict, delay_params: dict):
        """
        coinbase交易生成
        :param proof_info: 传入的dict数据
        :param delay_params: 用于VDF的参数信息
        :return: 返回生成的coinbase交易
        """
        tx = cls(b'')
        tx.proof_info = proof_info
        tx.delay_params = delay_params

        _input = CoinBaseInput('', -1, Config().get('node.public_key'))
        _input.proof_info = proof_info
        _input.delay_params = delay_params
        output = TxOutput(int(Config().get('node.coinbase_reward')),
                          Config().get('node.address'))
        tx = cls([_input], [output])
        tx.set_id(is_coinbase=True)
        logging.debug("Set coinbase tx hash: {}".format(tx.tx_hash))
        return tx