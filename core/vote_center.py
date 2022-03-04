import threading

from core.block_chain import BlockChain
from core.pot import ProofOfTime
from utils.singleton import Singleton


class VoteCenter(Singleton):
    def __init__(self):
        bc = BlockChain()
        block, _ = bc.get_latest_block()
        if block is not None:
            self.__local_height = block.block_header.height
        else:
            self.__local_height = -1

        self.__has_voted = False
        self.__final_address = None
        self.__vote = {}
        self.__lock = threading.Lock()
        self.__lock_height = threading.Lock()
        self.__lock_vote = threading.Lock()

    def refresh_height(self, latest_height):
        self.__lock_height.acquire()
        self.__local_height = latest_height
        self.__final_address = None
        self.__has_voted = False
        self.__lock_height.release()

    def clear(self):
        self.__lock_vote.acquire()
        self.__vote.clear()
        self.__lock_vote.release()

    def vote(self, height):
        self.__lock.acquire()
        if height > self.__local_height:
            self.refresh_height(height)

        if not self.__has_voted:
            pot = ProofOfTime()
            final_address = pot.local_vote()
            self.__final_address = final_address
        result = self.__final_address
        self.__lock.release()
        return result

    def vote_update(self, address, final_address):
        self.__lock_vote.acquire()
        if final_address not in self.__vote:
            self.__vote[final_address] = [address, 1]
        else:
            vote_list = self.__vote[final_address]
            if address not in vote_list:
                self.__vote[final_address].insert(0, address)
                vote_list[-1] += 1
        self.__lock_vote.release()

    def vote_sync(self, vote_data):
        self.__lock_vote.acquire()
        for address in vote_data:
            self.__vote[address] = vote_data[address]
        self.__lock_vote.release()

    @property
    def vote(self):
        return self.__vote
