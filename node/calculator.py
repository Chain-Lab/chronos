import binascii
import threading

from core.block_chain import BlockChain
from utils.singleton import Singleton
from utils import number_theory


class Calculator(Singleton):
    def __init__(self):
        self.changed = False
        self.seed = None
        self.order = None
        self.time_parma = None
        self.proof_parma = None

        self.result = None
        self.proof = None

    def change(self, new_seed):
        """
        得到区块中的vdf参数进行比对， 如果发生改变则重新开始计算
        """
        self.seed = new_seed
        self.changed = True

    def __initialization(self):
        """
        初始化函数， 获取到创世区块并拿到创世区块中的参数用于进行计算
        """
        bc = BlockChain()
        genesis_block = bc.get_block_by_height(0)
        coinbase_tx = genesis_block.transactions[0]
        coinbase_tx_input = coinbase_tx.inputs[0]
        delay_params = coinbase_tx_input.get("delay_params", {})
        order_hex = delay_params.get("order")
        verify_param = delay_params.get("verify_param")
        self.time_parma = delay_params.get("time_param")
        self.order = int.from_bytes(binascii.a2b_hex(bytes.fromhex(order_hex)), byteorder='big')
        self.proof_parma = int.from_bytes(binascii.a2b_hex(bytes.fromhex(verify_param)), byteorder='big')

        latest_block, _ = bc.get_latest_block()
        coinbase_tx_input = latest_block.transactions[0].inputs[0]
        delay_params = coinbase_tx_input.get("delay_params", {})
        # 先使用获取到的新的值作为这一轮的seed
        new_seed = int.from_bytes(binascii.a2b_hex(bytes.fromhex(delay_params.get("seed"))), byteorder='big')
        self.seed = new_seed

    def task(self):
        """
        用于计算VDF的线程函数， 目前设置参数保证一轮计算在30s左右
        """
        while True:
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
                self.result = result
                self.proof = pi
                self.seed = self.result
            else:
                self.changed = False

    def run(self):
        thread = threading.Thread(target=self.task, args=())
        thread.start()

    def verify(self, result, pi, seed):
        r = number_theory.quick_pow(2, self.time_parma, self.proof_parma)
        h = number_theory.quick_pow(pi, self.proof_parma, self.order) * number_theory.quick_pow(seed, r, self.order) % self.order
        return result == h
