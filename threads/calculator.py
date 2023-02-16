import logging
import threading

from core.block_chain import BlockChain
from utils import funcs
from utils import number_theory
from utils.b58code import Base58Code
from utils.singleton import Singleton

from utils import constant


class Calculator(Singleton):
    def __init__(self):
        self.order = None  # VDF计算的order, n = p * q
        self.time_parma = None  # 计算参数，从创世区块获取
        self.proof_parma = None

        self.seed = None  # 上一轮的计算结果，作为当前的计算输入
        self.proof = None  # 上一轮的证明参数
        self.result_seed = None  # 目前计算的结果
        self.result_proof = None  # 目前计算的证明参数

        self.__cond = threading.Condition()
        self.__lock = threading.Lock()
        self.__changed = False
        self.__has_inited = False
        self.__finished = False
        self.__initialization()

    def update(self, new_seed=None, pi=None):
        """
        得到区块中的vdf参数进行比对， 如果发生改变则重新开始计算
        """
        if new_seed == self.seed or self.__lock.locked():
            return

        if new_seed is None and not self.__finished:
            return

        self.__lock.acquire()
        logging.debug("VDF update locked.")

        if not self.__has_inited:
            with self.__cond:
                self.__initialization()
                logging.debug("Calculator initial finished.")
                self.__cond.notify_all()
        logging.info("VDF seed changed: {}, calculator status: {}".format(new_seed, self.__finished))

        if new_seed is not None:
            # 如果能进入到这个逻辑， 说明线程还在进行计算， seed没有被修改过
            # seed != new_seed, 修改changed之后立马会进行计算的重新开始
            self.seed = new_seed
            self.proof = pi
            if self.__finished:
                # 在本地计算完成后并且收到新的区块参数
                self.result_seed = None
                self.result_proof = None
                self.__finished = False
                # 计算完成的这个变量必须修改， 不然唤醒后继续循环
                with self.__cond:
                    logging.debug("Update remote VDF params, notify thread start calculate.")
                    self.__cond.notify_all()
            else:
                self.__changed = True
        else:
            # 本地作为打包节点时进行参数更新
            self.seed = self.result_seed
            self.proof = self.result_proof
            self.result_seed = None
            self.result_proof = None
            self.__finished = False
            with self.__cond:
                logging.debug("Update local VDF params, notify thread start calculate.")
                self.__cond.notify_all()
        self.__lock.release()
        logging.debug("VDF update release.")

    def __initialization(self):
        """
        初始化函数， 获取到创世区块并拿到创世区块中的参数用于进行计算
        """
        bc = BlockChain()
        genesis_block = bc.get_block_by_height(0)

        if genesis_block is None:
            logging.error("Genesis block is not exists.")
            return False

        coinbase_tx = genesis_block.transactions[0]
        delay_params = coinbase_tx.delay_params
        order_hex = delay_params.get("order")
        verify_param = delay_params.get("verify_param")
        self.time_parma = delay_params.get("time_param")
        self.order = funcs.hex2int(order_hex)
        self.proof_parma = funcs.hex2int(verify_param)
        logging.debug("Genesis params initial.")

        latest_block, _ = bc.get_latest_block()
        coinbase_tx_input = latest_block.transactions[0]
        delay_params = coinbase_tx_input.delay_params
        # 先使用获取到的新的值作为这一轮的seed
        new_seed = funcs.hex2int(delay_params.get("seed"))
        self.proof = funcs.hex2int(delay_params.get("proof", "00"))
        self.seed = new_seed
        self.__finished = False
        self.__has_inited = True
        return True

    def task(self):
        """
        用于计算VDF的线程函数， 目前设置参数保证一轮计算在30s左右
        todo： 这里存在问题，应该在下一个区块出来之前等待，如果更新了新的VDF参数再开始进行计算，否则存在一致性问题
        """
        while True:
            if not constant.NODE_RUNNING:
                logging.debug("Receive stop signal, stop thread.")
                break

            with self.__cond:
                # 没有创世区块无法初始化的时候
                while not self.__has_inited or self.__finished:
                    self.__cond.wait()
                calculated_round = 1
                g = self.seed
                result = self.seed
                pi, r = 1, 1
                while calculated_round <= self.time_parma:
                    if self.__changed:
                        break
                    result = result * result % self.order

                    # b in {0, 1}
                    b = 2 * r // self.proof_parma
                    r = 2 * r % self.proof_parma
                    pi = (pi * pi % self.order) * (g ** b % self.order)

                    calculated_round += 1
                if not self.__changed:
                    logging.debug("Local new seed calculate finished.")
                    with self.__lock:
                        self.result_seed = result
                        self.result_proof = pi
                        self.__finished = True
                else:
                    logging.debug("Seed changed. Start new calculate.")
                    self.__changed = False

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
        h = number_theory.quick_pow(pi, self.proof_parma, self.order) * number_theory.quick_pow(seed, r,
                                                                                                self.order) % self.order
        return result == h

    @property
    def delay_params(self):
        logging.debug("Calculator initial status: {}".format(self.__has_inited))
        if not self.__has_inited:
            with self.__cond:
                self.__initialization()
                self.__cond.notify_all()
        if self.__lock.locked():
            logging.debug("awaiting lock release...")
        self.__lock.acquire()

        if not self.__finished:
            logging.debug("seed: {}".format(self.seed))
            logging.debug("proof: {}".format(self.proof))
            result = {
                "seed": funcs.int2hex(self.seed),
                "proof": funcs.int2hex(self.proof)
            }
        else:
            result = {
                "seed": funcs.int2hex(self.result_seed),
                "proof": funcs.int2hex(self.result_proof)
            }
        self.__lock.release()
        logging.debug("Return result is :{}".format(result))
        return result

    def verify_address(self, address):
        """
        校验地址是否共识节点的地址
        :param address: 待校验的地址
        :return: 是否共识节点
        """
        if not self.__has_inited:
            with self.__cond:
                init_result = self.__initialization()
                self.__cond.notify_all()
            if not init_result:
                return False

        address_number = int.from_bytes(Base58Code.decode_check(address), byteorder='big')
        node_hash = self.seed * address_number % 2 ** 256

        if node_hash / 2 ** 256 > 1.0:
            logging.debug("{} is not consensus node.".format(address))
            return False

        return True
