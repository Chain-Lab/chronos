import binascii
import logging
import threading

from core.block_chain import BlockChain
from utils.b58code import Base58Code
from utils.singleton import Singleton
from utils import number_theory
from utils import funcs


class Calculator(Singleton):
    def __init__(self):
        self.changed = False
        self.seed = None
        self.order = None
        self.time_parma = None
        self.proof_parma = None

        self.result = None
        self.proof = None
        self.newest_seed = None

        self.__cond = threading.Condition()
        self.__has_inited = False
        self.__initialization()

    def update(self, new_seed):
        """
        得到区块中的vdf参数进行比对， 如果发生改变则重新开始计算
        """
        if new_seed == self.seed:
            return

        if not self.__has_inited:
            with self.__cond:
                self.__initialization()
                self.__cond.notify_all()

        logging.info("VDF seed changed: {}".format(new_seed))
        self.seed = new_seed
        self.newest_seed = new_seed
        self.changed = True

    def __initialization(self):
        """
        初始化函数， 获取到创世区块并拿到创世区块中的参数用于进行计算
        """
        bc = BlockChain()
        genesis_block = bc.get_block_by_height(0)

        if genesis_block is None:
            logging.error("Genesis block is not exists.")
            return

        coinbase_tx = genesis_block.transactions[0]
        coinbase_tx_input = coinbase_tx.inputs[0]
        delay_params = coinbase_tx_input.delay_params
        order_hex = delay_params.get("order")
        verify_param = delay_params.get("verify_param")
        self.time_parma = delay_params.get("time_param")
        self.order = funcs.hex2int(order_hex)
        self.proof_parma = funcs.hex2int(verify_param)

        latest_block, _ = bc.get_latest_block()
        coinbase_tx_input = latest_block.transactions[0].inputs[0]
        delay_params = coinbase_tx_input.delay_params
        # 先使用获取到的新的值作为这一轮的seed
        new_seed = funcs.hex2int(delay_params.get("seed"))
        self.result = new_seed
        self.newest_seed = new_seed
        self.proof = funcs.hex2int(delay_params.get("proof", "00"))
        self.seed = new_seed
        self.__has_inited = True

    def task(self):
        """
        用于计算VDF的线程函数， 目前设置参数保证一轮计算在30s左右
        todo： 这里存在问题，应该在下一个区块出来之前等待，如果更新了新的VDF参数再开始进行计算，否则存在一致性问题
        """
        while True:
            with self.__cond:
                while not self.__has_inited:
                    self.__cond.wait()
                calculated_round = 1
                g = self.seed
                result = self.seed
                pi, r = 1, 1
                while calculated_round <= self.time_parma:
                    if self.changed:
                        break
                    result = result * result % self.order

                    # b in {0, 1}
                    b = 2 * r // self.proof_parma
                    r = 2 * r % self.proof_parma
                    pi = (pi * pi % self.order) * (g ** b % self.order)

                    calculated_round += 1
                if not self.changed:
                    logging.debug("Local new seed calculate finished.")
                    self.result = result
                    self.proof = pi
                    self.seed = self.result
                else:
                    logging.debug("Seed changed. Start new calculate.")
                    self.changed = False

    def run(self):
        thread = threading.Thread(target=self.task, args=())
        thread.start()

    def verify(self, result, pi, seed):
        """
        验证VDF的计算结果是否正确，即Calculate(seed, t) == Verify(result, pi)
        :param result: 产生的新区块中包含的VDF结果
        :param pi: 验证参数
        :param seed: 原有seed
        :return:
        """
        r = number_theory.quick_pow(2, self.time_parma, self.proof_parma)
        h = number_theory.quick_pow(pi, self.proof_parma, self.order) * number_theory.quick_pow(seed, r, self.order) % self.order
        return result == h

    @property
    def delay_params(self):
        if not self.__has_inited:
            with self.__cond:
                self.__initialization()
                self.__cond.notify_all()

        self.newest_seed = self.result
        return {
            "seed": funcs.int2hex(self.result),
            "proof": funcs.int2hex(self.proof)
        }

    def verify_address(self, address):
        """
        校验地址是否共识节点的地址
        :param address: 待校验的地址
        :return: 是否共识节点
        """
        if not self.__has_inited:
            with self.__cond:
                self.__initialization()
                self.__cond.notify_all()

        address_number = int.from_bytes(Base58Code.decode_check(address), byteorder='big')
        node_hash = self.newest_seed * address_number % 2 ** 256

        if node_hash / 2 ** 256 > 0.3:
            logging.debug("{} is not consensus node.".format(address))
            return False

        return True
