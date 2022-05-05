import logging
import threading

from core.config import Config
from core.pot import ProofOfTime
from threads.calculator import Calculator
from utils.singleton import Singleton


class VoteCenter(Singleton):
    def __init__(self):
        self.__cond = threading.Condition()
        self.__vote_dict = {}
        # 汇总的投票信息
        self.__vote = {}
        self.__queue = []
        self.__height = 0
        self.__vote_height = 0

        self.__has_voted = False
        self.__final_address = None
        self.__vote_lock = threading.Lock()
        self.thread = threading.Thread(target=self.task, args=(), name="VoteCenterThread")
        self.thread.start()

    def vote_update(self, address: str, final_address: str, height: int):
        logging.debug("Trying append task {} vote {} height {}".format(address, final_address, height))

        # 先检查是否在字典中， 字典key查找操作o(1)
        if height < self.__height or address in self.__vote_dict.keys() or self.__vote_lock.locked():
            return

        logging.debug("Insert task to queue successful.")
        self.__vote_dict[address] = final_address
        with self.__cond:
            self.__queue.append(address)
            logging.debug("Notify to merge vote queue.")
            self.__cond.notify_all()

    def task(self):
        while True:
            with self.__cond:
                while not len(self.__queue):
                    self.__cond.wait()
                current = self.__queue.pop(0)
                address = current
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

    def refresh(self, height):
        logging.debug("Trying refresh vote center height #{} to new height #{}".format(self.__height, height))
        if height != self.__height + 1 or not self.__has_voted:
            logging.debug("Local vote status: {}".format(self.__has_voted))
            logging.debug("Vote lock status: {}".format("Locked" if self.__vote_lock.locked() else "Unlocked"))
            return

        self.__vote_lock.acquire()
        # 避免另外一个线程拿到锁后进行多余的操作
        if height < self.__height:
            self.__vote_lock.release()
            return
        logging.debug("Synced height #{}, latest height #{}, clear information.".format(self.__height, height))
        self.__height = height
        self.__queue.clear()
        self.__vote_dict.clear()
        self.__vote.clear()
        self.__has_voted = False
        self.__vote_lock.release()

    def local_vote(self):
        self.__vote_lock.acquire()
        if not self.__has_voted:
            pot = ProofOfTime()
            final_address = pot.local_vote()
            self.__has_voted = True
            self.__final_address = final_address
            logging.debug("Local address {} vote address {}.".format(Config().get("node.address"), final_address))
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


if __name__ == "__main__":
    import dis

    dis.dis(VoteCenter.refresh)
