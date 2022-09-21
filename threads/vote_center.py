import logging
import threading
from queue import Queue

from core.config import Config
from core.pot import ProofOfTime
from threads.calculator import Calculator
from utils.singleton import Singleton

from utils import constant


class VoteCenter(Singleton):
    def __init__(self):
        self.__cond = threading.Condition()
        self.__vote_dict = {}
        # 汇总的投票信息
        self.__vote = {}
        self.__queue = Queue()
        self.__height = 0 # 限制投票高度
        self.__vote_height = 0

        self.__has_voted = False # 在本轮是否投票过
        self.__rolled_back = False # 本轮投票时是否回退过
        self.__final_address = None # 投票的目标地址
        self.__vote_lock = threading.Lock() # 投票锁
        self.thread = threading.Thread(target=self.task, args=(), name="VoteCenterThread")
        self.thread.start()

    def vote_update(self, address: str, final_address: str, height: int):
        '''
        往投票中心的队列中添加投票信息
        @param address: 投票地址
        @param final_address: 目标地址
        @param height: 该次投票高度
        @return:
        '''
        # logging.debug("Trying append task {} vote {} height {}".format(address, final_address, height))

        # 先检查是否在字典中， 字典key查找操作o(1)
        if height < self.__height or address in self.__vote_dict or self.__vote_lock.locked():
            logging.debug("Address " + " in dict." if address in self.__vote_dict else " not in dict.")
            logging.debug("Vote lock status: {}".format("Locked" if self.__vote_lock.locked() else "Unlocked"))
            return

        logging.debug("Insert task to queue successful.")
        self.__vote_dict[address] = final_address
        with self.__cond:
            self.__queue.put(address)
            logging.debug("Notify to merge vote queue.")
            self.__cond.notify_all()

    def task(self):
        '''
        投票队列处理线程函数
        @return:
        '''
        while True:
            if not constant.NODE_RUNNING:
                logging.debug("Receive stop signal, stop thread.")
                break

            with self.__cond:
                while self.__queue.empty():
                    self.__cond.wait()
                current = self.__queue.get()
                address = current

                if address not in final_address:
                    continue

                final_address = self.__vote_dict[address]
                logging.debug("Pop task {} vote {}".format(address, final_address))

                if address == final_address or not Calculator().verify_address(address):
                    continue

                if final_address not in self.__vote:
                    self.__vote[final_address] = [address, 1]
                else:
                    vote_list = self.__vote[final_address]
                    if address not in vote_list:
                        self.__vote[final_address].insert(0, address)
                        vote_list[-1] += 1

    def vote_sync(self, vote_data: dict, height: int):
        for final_address in vote_data.keys():
            length = len(vote_data[final_address])
            for i in range(length - 1):
                self.vote_update(vote_data[final_address][i], final_address, height)

    def refresh(self, height, rolled_back=False):
        '''
        刷新投票中心
        @param height: 刷新的高度
        @param rolled_back: 是否为回退操作
        @return:
        '''

        # 刷新高度的条件：本次刷新是在回退后刷新 或 高度高于目前高度
        logging.debug("Trying refresh vote center height #{} to new height #{}".format(self.__height, height))
        if not rolled_back and height <= self.__height:
            # or (not self.__has_voted and not self.__rolled_back):
            # 在下面的两种情况下进行投票
            # 如果非回退区块的情况下， 高度还小于等于目前高度
            # 本地没有进行过投票， 且非回退操作
            logging.debug("Local vote status: {}".format(self.__has_voted))
            logging.debug("Vote lock status: {}".format("Locked" if self.__vote_lock.locked() else "Unlocked"))
            return False

        self.__vote_lock.acquire()

        self.__rolled_back = rolled_back

        logging.debug("Synced height #{}, latest height #{}, clear information.".format(self.__height, height))
        self.__height = height

        with self.__queue.mutex:
            self.__queue.queue.clear()

        self.__vote_dict.clear()
        self.__vote.clear()
        while not self.__queue.empty():
            self.__queue.get()
        self.__has_voted = False
        self.__vote_lock.release()

        return True

    def local_vote(self, height):
        self.__vote_lock.acquire()

        if height < self.__height:
            self.__vote_lock.release()
            # 返回值需要进行修改
            return -1

        if not self.__has_voted:
            pot = ProofOfTime()
            final_address = pot.local_vote()
            self.__has_voted = True
            self.__final_address = final_address
            logging.debug("Local address {} vote address {}.".format(Config().get("node.address"), final_address))
        else:
            logging.debug("Return vote result directly.")
        result = self.__final_address
        self.__vote_lock.release()
        return result

    @property
    def vote(self):
        return self.__vote

    @property
    def has_vote(self):
        return self.__has_voted

    @property
    def height(self):
        return self.__height

    @property
    def rolled_back(self):
        return self.__rolled_back
