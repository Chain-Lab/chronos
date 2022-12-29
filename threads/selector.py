import logging
import queue
import threading

from core.block_chain import BlockChain
from node.timer import Timer
from threads.calculator import Calculator
from utils import funcs
from utils.singleton import Singleton


class Selector(Singleton):
    def __init__(self):
        self.__height = -1
        self.__blocks = {}
        self.__selected_block = None
        self.__select_lock = threading.RLock()

    def compare_block(self, block):
        block_hash = block.hash
        if block.height != self.__height + 1 or block_hash in self.__blocks:
            return

        with self.__select_lock:
            if block.height != self.__height + 1 or block_hash in self.__blocks:
                return

            if not self.__selected_block:
                if Selector().__check_block_timeout(block):
                    logging.warning("Block timeout.")
                    return

                self.__selected_block = block
                self.__blocks[block_hash] = block
                return

            block_prev_hash = block.block_header.prev_block_hash
            block_count = block.vote_count
            block_timestamp = block.block_header.timestamp

            equal_block = self.__selected_block
            equal_count = equal_block.vote_count
            equal_hash = equal_block.block_header.hash
            equal_timestamp = equal_block.block_header.timestamp
            equal_prev_hash = equal_block.block_header.prev_block_hash

            if block_hash == equal_hash or block_prev_hash != equal_prev_hash or block_count < equal_count or (
                    block_count == equal_count and block_timestamp > equal_timestamp):
                logging.info("block #{} < block #{}.".format(block_hash, equal_block.hash))
                return

            self.__selected_block = block

    def insert_block(self):
        if not self.__selected_block:
            return

        with self.__select_lock:
            block_height = self.__selected_block.height
            block = self.__selected_block
            BlockChain().insert_block(self.__selected_block)
            Timer().refresh()
            delay_params = block.transactions[0].inputs[0].delay_params
            hex_seed = delay_params.get("seed")
            hex_pi = delay_params.get("proof")
            seed = funcs.hex2int(hex_seed)
            pi = funcs.hex2int(hex_pi)
            Calculator().update(seed, pi)
            self.refresh(block_height)

    def refresh(self, height):
        with self.__select_lock:
            self.__blocks.clear()
            self.__height = height
            self.__selected_block = None

    @staticmethod
    def __check_block_timeout(block):
        genesis = BlockChain().get_block_by_height(0)
        genesis_timestamp = int(genesis.block_header.timestamp)
        block_timestamp = int(block.block_header.timestamp)
        block_height = block.block_header.height

        return (block_height - 1) * 15 * 1000 + genesis_timestamp + 13500 < block_timestamp

    @property
    def height(self):
        return self.__height
