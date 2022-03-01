import logging
from configparser import ConfigParser, NoOptionError

from utils.singleton import Singleton


class Config(Singleton):
    def __init__(self):
        self.parser = ConfigParser()
        self.parser.read("config.ini", "utf-8")
        logging.info("Config file loaded.")

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


if __name__ == "__main__":
    print(type(Config().get("node.mem_pool_size")))
