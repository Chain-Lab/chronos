import threading


# 单例父类
class Singleton(object):
    _instance_lock = threading.Lock()
    __instance = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            # 如果实例不存在， 创建实例
            with Singleton._instance_lock:
                cls.__instance = super(
                    Singleton, cls).__new__(cls)
        else:
            # 如果实例存在，说明已经初始化过了， pass掉__init__
            # fixed: 多线程的情况下多次__init__导致出现NoneType问题
            def init_pass(self, *args, **kwargs):
                pass

            cls.__init__ = init_pass

        return cls.__instance