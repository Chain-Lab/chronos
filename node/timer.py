import threading
import time

from utils.singleton import Singleton


class Timer(Singleton):
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
