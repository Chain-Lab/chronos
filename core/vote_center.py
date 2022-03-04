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
        self.__lock = threading.Lock()

    def refresh_height(self, latest_height):
        self.__lock.acquire()
        self.__local_height = latest_height
        self.__final_address = None
        self.__has_voted = False
        self.__lock.release()

    def clear(self):
        self.__final_address = None
        self.__has_voted = False

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
