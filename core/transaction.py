import binascii
import copy
import logging

import ecdsa

from core.config import Config
from utils import funcs


class Transaction(object):
    def __init__(self, inputs, outputs):
        self.tx_hash = ''
        self.inputs = inputs
        self.outputs = outputs

    def set_id(self):
        """
        设置当前交易的交易id，根据输入和输出的数据哈希得到
        :return: None
        """
        data_list = [str(_) for _ in self.inputs]
        output_list = [str(_) for _ in self.outputs]
        data_list.extend(output_list)
        data = ''.join(data_list)
        logging.debug(data)
        tx_hash = funcs.sum256_hex(data)
        self.tx_hash = tx_hash

    def is_coinbase(self):
        """
        判断当前的交易是否是coinbase交易
        根据输入只有一个且输入的交易id向量为0以及没有输出来进行判断
        :return: 如果是coinbase交易， 返回True
        """
        return len(self.inputs) == 1 and len(self.inputs[0].tx_hash) == 0 and self.inputs[0].index == -1

    def verify(self, prev_txs):
        """
        todo: 存在coinbase交易时需要修改vote_info， 通过openapi是无法获取到投票信息的
        对交易进行验证, 填入链上的输出地址进行验证， 而提交的交易由提交者自己填入地址
        :param prev_txs: 当前交易的各个input对应哈希的交易
        :return: 验证是否通过
        """
        if self.is_coinbase():
            return True

        tx_copy = copy.deepcopy(self)

        for idx, _input in enumerate(self.inputs):
            prev_tx = prev_txs.get(_input.tx_hash, None)
            if not prev_tx:
                raise ValueError('Previous transaction error.')
            tx_copy.inputs[idx].signature = None
            tx_copy.inputs[idx].pub_key = prev_tx.outputs[_input.index].pub_key_hash
            tx_copy.set_id()
            tx_copy.inputs[idx].pub_key = None

            signature = binascii.a2b_hex(self.inputs[idx].signature)
            vk = ecdsa.VerifyingKey.from_string(binascii.a2b_hex(_input.pub_key), curve=ecdsa.SECP256k1)

            if not vk.verify(signature, tx_copy.tx_hash.encode()):
                return False

        return True

    def serialize(self):
        """
        序列化， 将交易id、输入列表、输出列表导出为dict
        :return: 序列化后的字典
        """
        return {
            "tx_hash": self.tx_hash,
            "inputs": [_.serialize() for _ in self.inputs],
            "outputs": [_.serialize() for _ in self.outputs]
        }

    @classmethod
    def deserialize(cls, data: dict):
        """
        反序列化, 先按照原有的方法进行反序列化
        todo: 后续测试是否可以使用__dict__.update来进行反序列化赋值
        :param data:
        :return:
        """
        tx_hash = data.get('tx_hash', '')
        inputs_data = data.get('inputs', [])
        outputs_data = data.get('outputs', [])
        inputs = []
        outputs = []
        is_coinbase = True

        for input_data in inputs_data:
            if is_coinbase:
                inputs.append(CoinBaseInput.deserialize(input_data))
            else:
                inputs.append(TxInput.deserialize(input_data))

            is_coinbase = False

        for output_data in outputs_data:
            outputs.append(TxOutput.deserialize(output_data))

        tx = cls(inputs, outputs)
        tx.tx_hash = tx_hash
        return tx

    @classmethod
    def coinbase_tx(cls, data: dict):
        """
        coinbase交易生成
        :param data: 传入的dict数据
        :return: 返回生成的coinbase交易
        """
        vote_node = data
        _input = CoinBaseInput('', -1, Config().get('node.public_key'))
        _input.vote_info = vote_node
        output = TxOutput(int(Config().get('node.coinbase_reward')),
                         Config().get('node.address'))
        tx = cls([_input], [output])
        tx.set_id()
        return tx

    def __repr__(self):
        return 'Transaction(tx_hash={}, ' \
               'inputs={}, ' \
               'outputs={})'.format(self.tx_hash, self.inputs, self.outputs)


class TxInput(object):
    def __init__(self, tx_hash=None, index=None, pub_key=None):
        """
        :param tx_hash: input的交易hash
        :param index: 对应交易的index
        :param pub_key: input的签名公钥
        """
        self.tx_hash = tx_hash
        self.index = index
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
        result = self.__dict__
        if "vote_info" in self.__dict__.keys():
            result.pop("vote_info")
        return str(result)

    # 直接更新dict进行初始化, 后面需要通过json-schema校验
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
    def __init__(self, tx_hash=None, inputs=None, outputs=None):
        super().__init__(tx_hash, inputs, outputs)
        self.vote_info = {}

    def set_vote(self, address, node_id, vote_count, vote_node):
        self.vote_info[address] = {}
        self.vote_info[address]['node_id'] = node_id
        self.vote_info[address]['vote_count'] = vote_count
        self.vote_info[address][vote_node] = vote_node

    def __repr__(self):
        """
        重写方法， 相比tx_input多了投票信息, 去掉投票信息
        """
        result = self.__dict__
        if "vote_info" in self.__dict__.keys():
            result.pop("vote_info")
        return str(result)
