import binascii

import ecdsa

from utils import funcs
from core.config import Config


class Transaction(object):
    def __init__(self, vins, vouts):
        self.txid = ''
        self.vins = vins
        self.vouts = vouts

    def set_id(self):
        """
        设置当前交易的交易id，根据输入和输出的数据哈希得到
        :return: None
        """
        data_list = [str(vin) for vin in self.vins]
        vout_list = [str(vout) for vout in self.vouts]
        data_list.extend(vout_list)
        data = ''.join(data_list)
        hash = funcs.sum256_hex(data)
        self.txid = hash

    def is_coinbase(self):
        """
        判断当前的交易是否是coinbase交易
        根据输入只有一个且输入的交易id向量为0以及没有输出来进行判断
        :return: 如果是coinbase交易， 返回True
        """
        return len(self.vins) == 1 and len(self.vins[0].txid) == 0 and self.vins[0].vout == -1

    def __trimmed_copy(self):
        inputs = []
        outputs = []

        for vin in self.vins:
            inputs.append(TxInput(vin.txid, vin.vout, None))

        for vout in self.vouts:
            outputs.append(TxOutput(vout.value, vout.pub_key_hash))

        result = Transaction(inputs, outputs)
        result.txid = self.txid
        return result

    def verify(self, prev_txs):
        if self.is_coinbase():
            return True

        tx_copy = self.__trimmed_copy()

        for index, vin in enumerate(tx_copy.vins):
            prev_tx = prev_txs.get(vin.txid, None)
            if not prev_tx:
                raise ValueError('Previous transaction error.')
            tx_copy.vins[index].signature = None
            tx_copy.vins[index].pub_key = prev_tx.vouts[vin.vout].pub_key_hash
            tx_copy.set_id()
            tx_copy.vins[index].pub_key = None

            signature = binascii.a2b_hex(self.vins[index].signature)
            vk = ecdsa.VerifyingKey.from_string(binascii.a2b_hex(vin.pub_key), curve=ecdsa.SECP256k1)


            if not vk.verify(signature, tx_copy.txid.encode()):
                return False

        return True

    def serialize(self):
        """
        序列化， 将交易id、输入列表、输出列表导出为dict
        :return: 序列化后的字典
        """
        return {
            "txid": self.txid,
            "vins": [vin.serialize() for vin in self.vins],
            "vouts": [vout.serialize() for vout in self.vouts]
        }

    @classmethod
    def deserialize(cls, data: dict):
        """
        反序列化, 先按照原有的方法进行反序列化
        todo: 后续测试是否可以使用__dict__.update来进行反序列化赋值
        :param data:
        :return:
        """
        txid = data.get('txid', '')
        vins_data = data.get('vins', [])
        vouts_data = data.get('vouts', [])
        vins = []
        vouts = []
        is_coinbase = True

        for vin_data in vins_data:
            if is_coinbase:
                vins.append(CoinBaseInput.deserialize(vin_data))
            else:
                vins.append(TxInput.deserialize(vin_data))

        for vout_data in vouts_data:
            vouts.append(TxOutput.deserialize(vout_data))

        tx = cls(vins, vouts)
        tx.txid = txid
        return tx

    @classmethod
    def coinbase_tx(cls, data):
        vote_node = data
        txin = CoinBaseInput('', -1, Config().get('node.public_key'))
        txin.vote_info = vote_node
        txout = TxOutput(int(Config().get('node.coinbase_reward')),
                         Config().get('node.address'))
        tx = cls([txin], [txout])
        tx.set_id()
        return tx

    def __repr__(self):
        return 'Transaction(txid={}, ' \
               'vins={}, ' \
               'vouts={})'.format(self.txid, self.vins, self.vouts)


class TxInput(object):
    def __init__(self, txid=None, vout=None, pub_key=None):
        self.txid = txid
        self.vout = vout
        self.signature = ''
        self.pub_key = pub_key

    def usr_key(self, pub_key_hash):
        """
        todo: 检查该函数的用途
        :param pub_key_hash: 16进制字符串类型的公钥
        :return:
        """
        bin_pub_key = binascii.a2b_hex(self.pub_key)
        pub_hash = funcs.hash_public_key(bin_pub_key)
        return pub_key_hash == pub_hash

    def serialize(self):
        return self.__dict__

    def __repr__(self):
        # 先直接输出json信息， 后面再重新进行修改
        return str(self.__dict__)

    # 直接更新dict进行初始化
    @classmethod
    def deserialize(cls, data: dict):
        result = cls()
        result.__dict__.update(data)
        return result


class TxOutput(object):
    def __init__(self, value=0, pub_key_hash=''):
        self.value = value
        self.pub_key_hash = pub_key_hash

    def lock(self, address):
        hex_pub_key_hash = binascii.b2a_hex(
            funcs.address_to_pubkey_hash(address)
        )
        self.pub_key_hash = hex_pub_key_hash

    def is_locked(self, pub_key_hash):
        return self.pub_key_hash == pub_key_hash

    def serialize(self):
        return self.__dict__

    def __repr__(self):
        return str(self.__dict__)

    @classmethod
    def deserialize(cls, data: dict):
        result = cls()
        result.__dict__.update(data)
        return result


class CoinBaseInput(TxInput):
    def __init__(self, txid=None, vout=None, pub_key=None):
        super().__init__(txid, vout, pub_key)
        self.vote_info = {}

    def set_vote(self, address, node_id, vote_count, vote_node):
        self.vote_info[address] = {}
        self.vote_info[address]['node_id'] = node_id
        self.vote_info[address]['vote_count'] = vote_count
        self.vote_info[address][vote_node] = vote_node

