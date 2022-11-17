from abc import abstractmethod, ABC


class DBInterface(ABC):

    @property
    @abstractmethod
    def db(self):
        """
        获取数据库对象实例
        """

    @abstractmethod
    def get(self, key, default=None):
        """
        获取 key 对应的 value
        """

    @abstractmethod
    def insert(self, _key: str, _value: dict) -> bool:
        """
        插入新的键值对
        """

    @abstractmethod
    def remove(self, _key: str) -> bool:
        """
        从数据库中移除键对应的数据
        """

    @abstractmethod
    def batch_insert(self, kv_data: dict):
        """
        批量插入数据
        """

    @abstractmethod
    def batch_remove(self, keys: list):
        """
        批量移除数据
        """