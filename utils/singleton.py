import threading


# 单例父类, 目前存在问题， 子类的__init__会被调用两次
class Singleton(object):
    _instance_lock = threading.Lock()
    __instance = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            with Singleton._instance_lock:
                cls.__instance = super(
                    Singleton, cls).__new__(cls)
        return cls.__instance
