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
        self.__leveldb = Config.get("leveldb.path")

    @property
    def db(self):
        if not self.__db:
            self.__db = plyvel.DB(self.__leveldb, bool_create_if_missing=True)

        return self.__db

    def insert(self, _key: str, _value: dict) -> bool:
        self.__db: plyvel.DB

        # bytes_value = rlp.encode(_value)
        bytes_value = bytes(json.dumps(_value), "utf-8")
        bytes_key = bytes(_key, 'utf-8')

        try:
            self.__db.put(bytes_key, bytes_value)
        except Exception as e:
            logging.error(e)
            return False

        return True

    def remove(self, _key: str) -> bool:
        self.__db: plyvel.DB
        bytes_key = bytes(_key, 'utf-8')
        try:
            self.__db.delete(bytes_key)
        except Exception as e:
            logging.error(e)
            return False

        return True

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
        # 声明类型便于后面调用方法
        self.__db: plyvel.DB

        with self.__db.write_batch() as wb:
            for key in kv_data:
                bytes_key = bytes(key, "utf-8")
                # bytes_value = rlp.encode(kv_data[bytes_key])
                bytes_value = bytes(json.dumps(kv_data[bytes_key]), "utf-8")
                wb.put(bytes_key, bytes_value)

    def batch_remove(self, keys: list):
        self.__db: plyvel.DB

        with self.__db.write_batch() as wb:
            for key in keys:
                bytes_key = bytes(key, "utf-8")
                wb.delete(bytes_key)

    def __getattr__(self, key):
        return getattr(self.__db, key)

    def __contains__(self, key):
        return self.__db.__contains__(key)

    def __getitem__(self, key: str):
        self.__db: plyvel.DB
        bytes_data: bytes

        bytes_key = bytes(key, "utf-8")
        bytes_data = self.__db.get(bytes_key)

        return json.loads(bytes_data.decode())

    def __del__(self):
        self.__db.close()