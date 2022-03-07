import logging
import os
import random
import binascii
from configparser import ConfigParser, NoOptionError
from ecdsa import SigningKey, SECP256k1

from utils import funcs
from utils.b58code import Base58Code
from utils.singleton import Singleton


class Config(Singleton):
    def __init__(self):
        self.parser = ConfigParser()
        self.path = "./conf/config.ini"
        if os.path.exists(self.path):
            self.parser.read("./conf/config.ini", "utf-8")
        else:
            self.__initialization()
            self.parser.read("./conf/config.ini", "utf-8")
        logging.info("Config file loaded.")

    def __initialization(self):
        self.parser.read("./template/config.ini")
        node_id = random.randint(2, 100)

        # 生成本地密钥对
        sign_key = SigningKey.generate(curve=SECP256k1)
        public_key = sign_key.get_verifying_key()

        private_address = b'\0' + funcs.hash_public_key(public_key.to_string())
        address = Base58Code.encode_check(private_address).decode()

        public_key = binascii.b2a_hex(public_key.to_string()).decode()

        self.set("node.address", address)
        self.set("node.public_key", public_key)
        self.set("node.listen_ip", "0.0.0.0")
        self.set("node.id", str(node_id))
        self.set("node.is_bootstrap", str(0))

    def get(self, key: str, default=None):
        """
        :param key: 键值，格式为[section].[key]
        :param default: 在发生错误情况下返回的默认值
        :return: default或配置文件中的值, str类型
        """
        map_key = key.split('.')
        if len(map_key) < 2:
            return default

        section = map_key[0]
        if not self.parser.has_section(section):
            return default

        option = '.'.join(map_key[1:])
        try:
            return self.parser.get(section, option)
        except NoOptionError:
            return default

    def set(self, key: str, value: str):
        map_key = key.split('.')
        if len(map_key) < 2:
            return
        section = map_key[0]
        if not self.parser.has_section(section):
            return

        option = '.'.join(map_key[1:])
        self.parser.set(section, option, value)

    def save(self):
        with open(self.path, "w") as config_file:
            self.parser.write(config_file)


if __name__ == "__main__":
    print(type(Config().get("node.mem_pool_size")))
