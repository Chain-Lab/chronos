import json

import plyvel
import rlp
import logging

from interfaces.DBInterface import DBInterface
from utils.singleton import Singleton
from core.config import Config


class LevelDB(DBInterface, Singleton):
    def __init__(self):
        self.__db = None
        self.__leveldb = Config().get("leveldb.path")

    @property
    def db(self) -> plyvel.DB:
        if not self.__db:
            self.__db = plyvel.DB(self.__leveldb, create_if_missing=True)

        return self.__db

    def insert(self, _key: str, _value: dict) -> bool:
        # bytes_value = rlp.encode(_value)
        bytes_value = bytes(json.dumps(_value), "utf-8")
        bytes_key = bytes(_key, 'utf-8')

        try:
            self.db.put(bytes_key, bytes_value)
        except Exception as e:
            logging.error(e)
            return False

        return True

    def remove(self, _key: str) -> bool:
        bytes_key = bytes(_key, 'utf-8')
        try:
            self.db.delete(bytes_key)
        except Exception as e:
            logging.error(e)
            return False

        return True

    def get(self, key, default=None):
        bytes_key = bytes(key, "utf-8")
        bytes_data = self.db.get(bytes_key)

        if not bytes_data:
            return default
        return json.loads(bytes_data.decode())


    def batch_insert(self, kv_data: dict):
        """
        考虑后面挪到一个文档中说明
        kv_data format:
        {
            "key1": {value_dict},
            "key2": {value_dict},
            ...
        }
        """
        with self.db.write_batch() as wb:
            for key in kv_data:
                bytes_key = bytes(key, "utf-8")
                # bytes_value = rlp.encode(kv_data[bytes_key])
                bytes_value = bytes(json.dumps(kv_data[key]), "utf-8")
                wb.put(bytes_key, bytes_value)

    def batch_remove(self, keys: list):
        with self.db.write_batch() as wb:
            for key in keys:
                bytes_key = bytes(key, "utf-8")
                wb.delete(bytes_key)

    def __getattr__(self, key):
        return getattr(self.db, key)

    def __getitem__(self, key: str):
        bytes_key = bytes(key, "utf-8")
        bytes_data = self.db.get(bytes_key)

        if not bytes_data:
            return None
        return json.loads(bytes_data.decode())

    def __setitem__(self, key, value):
        self.insert(key, value)

    def __del__(self):
        self.db.close()