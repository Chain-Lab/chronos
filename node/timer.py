import threading
import time

from utils.singleton import Singleton
from core.block_chain import BlockChain


class Timer(Singleton):
    """
    节点的计时器， 在间隔时间后触发共识逻辑
    """
    INTERVAL = 30
    FINISH_INTERVAL = 10
    # 便于调试，先设置为30秒

    def __init__(self):
        self.__next_time = -1
        self.__finish_time = -1
        self.__height = -1

        self.__lock = threading.Lock()
        self.__initialization()

    def __initialization(self):
        """
        初始化函数
        return:
        """
        bc = BlockChain()
        latest_block, _ = bc.get_latest_block()
        timer = Timer()
        height = latest_block.block_header.height
        timestamp = latest_block.block_header.height
        timer.refresh(height=height, timestamp=timestamp)
        self.refresh(height, timestamp)

    def refresh(self, height, timestamp=None):
        if self.__lock.locked() or height <= self.__height:
            return

        self.__lock.acquire()

        if timestamp is None:
            timestamp = time.time()
        else:
            timestamp = timestamp // 1000

        self.__height = height
        self.__next_time = timestamp + Timer.INTERVAL
        self.__finish_time = self.__next_time + Timer.FINISH_INTERVAL
        self.__lock.release()

    def reach(self):
        now = time.time()

        if self.__next_time < 0:
            return False

        return now >= self.__next_time

    def finish(self):
        now = time.time()
        if self.__next_time <= 0:
            return False

        return now >= self.__finish_time
