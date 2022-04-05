import threading
import time

from utils.singleton import Singleton


class Timer(Singleton):
    """
    节点的计时器， 在间隔时间后触发共识逻辑
    """
    INTERVAL = 30
    # 便于调试，先设置为30秒

    def __init__(self):
        self.__next_time = -1
        self.__height = -1

        self.__lock = threading.Lock()

    def refresh(self, height):
        if self.__lock.locked() or height <= self.__height:
            return

        self.__lock.acquire()
        self.__height = height
        self.__next_time = time.time() + Timer.INTERVAL
        self.__lock.release()

    def reach(self):
        now = time.time()

        if self.__next_time < 0:
            return False

        return now >= self.__next_time
