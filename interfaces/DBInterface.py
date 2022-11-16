from abc import abstractmethod, ABC


class DBInterface(ABC):

    @property
    @abstractmethod
    def db(self):
        """
        Get database util instance
        """

    @abstractmethod
    def insert(self, _key: str, _value: dict) -> bool:
        """
        Insert new data (_value) with (_key)
        """

    @abstractmethod
    def remove(self, _key: str) -> bool:
        """
        Remove data with (key)
        """

    @abstractmethod
    def batch_insert(self, kv_data: dict):
        """
        Batch insert data to database
        """

    @abstractmethod
    def batch_remove(self, keys: list):
        """
        Batch remove data from database
        """