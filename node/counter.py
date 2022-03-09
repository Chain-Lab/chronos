import threading
import logging

from utils.singleton import Singleton


class Counter(Singleton):
    def __init__(self):
        self.__client_count = 0
        self.__client_synced = 0
        self.__lock = threading.Lock()

    def client_reg(self):
        self.__lock.acquire()
        self.__client_count += 1
        self.__lock.release()

    def client_close(self):
        self.__lock.acquire()
        self.__client_count -= 1
        logging.debug("Client connect closed, ")
        self.__lock.release()

    def client_synced(self):
        self.__lock.acquire()
        self.__client_synced += 1
        self.__lock.release()

    def client_verify(self):
        return self.__client_count == self.__client_synced
