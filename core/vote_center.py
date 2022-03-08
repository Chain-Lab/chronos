import threading
import logging

from core.block_chain import BlockChain
from core.pot import ProofOfTime
from utils.singleton import Singleton


class VoteCenter(Singleton):
    def __init__(self):
        self.__has_voted = False
        self.__final_address = None
        self.__vote = {}
        # todo: client连接信息统计， 需解耦

        self.__client_count = 0
        self.__client_synced = 0

        self.__lock = threading.Lock()
        self.__lock_height = threading.Lock()
        self.__lock_vote = threading.Lock()
        self.__lock_client = threading.Lock()

        bc = BlockChain()
        block, _ = bc.get_latest_block()
        if block is not None:
            self.__local_height = block.block_header.height
        else:
            self.__local_height = -1

    def refresh_height(self, latest_height):
        # 如果vote_center中的两个锁都被锁，直接返回
        if self.__lock_height.locked() or self.__lock_client.locked():
            return

        self.__lock_height.acquire()
        self.__local_height = latest_height
        self.__final_address = None
        self.__has_voted = False
        self.__vote.clear()
        self.__lock_height.release()

        self.__lock_client.acquire()
        self.__client_synced = 0
        self.__lock_client.release()

    def clear(self):
        self.__lock_vote.acquire()
        self.__vote.clear()
        self.__has_voted = False
        self.__lock_vote.release()

    def local_vote(self):
        self.__lock.acquire()
        if not self.__has_voted:
            pot = ProofOfTime()
            final_address = pot.local_vote()
            self.__has_voted = True
            self.__final_address = final_address
        result = self.__final_address
        self.__lock.release()
        return result

    def vote_update(self, address, final_address):
        self.__lock_vote.acquire()
        if final_address not in self.__vote:
            self.__vote[final_address] = [address, 1]
            logging.debug("Vote center update {} vote {}".format(address, final_address))
        else:
            vote_list = self.__vote[final_address]
            if address not in vote_list:
                self.__vote[final_address].insert(0, address)
                vote_list[-1] += 1
                logging.debug("Vote center update {} vote {}".format(address, final_address))
        self.__lock_vote.release()

    def vote_sync(self, vote_data):
        for final_address in vote_data.keys():
            length = len(vote_data[final_address])
            for i in range(length - 1):
                self.vote_update(vote_data[final_address][i], final_address)

    def client_reg(self):
        self.__lock_client.acquire()
        self.__client_count += 1
        self.__lock_client.release()

    def client_close(self):
        self.__lock_client.acquire()
        self.__client_count -= 1
        logging.debug("Client connect closed, ")
        self.__lock_client.release()

    def client_synced(self):
        self.__lock_client.acquire()
        self.__client_synced += 1
        self.__lock_client.release()

    def client_verify(self):
        return self.__client_count == self.__client_synced

    @property
    def vote(self):
        return self.__vote

    @property
    def has_vote(self):
        return self.__has_voted
