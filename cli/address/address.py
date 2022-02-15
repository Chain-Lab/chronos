import binascii
import json

from ecdsa import SigningKey, SECP256k1
from utils.b58code import Base58Code
from utils import funcs


class Address(object):
    __VERSION = b'\0'

    def __init__(self):
        self.__private_key = None
        self.__public_key = None
        self.__address = None

    @property
    def __hash_public_key(self):
        return funcs.hash_public_key(self.__public_key.to_string())

    def __generate(self, curve=SECP256k1):
        sign_key = SigningKey.generate(curve=curve)
        self.__private_key = sign_key
        self.__public_key = sign_key.get_verifying_key()

        private_address = self.__VERSION + self.__hash_public_key
        self.__address = Base58Code.encode_check(private_address).decode()

    def generate(self):
        self.__generate()
        result = {
            "prv": binascii.b2a_hex(self.__private_key.to_string()).decode(),
            "pub": binascii.b2a_hex(self.__public_key.to_string()).decode(),
            "address": self.__address
        }
        return json.dumps(result, indent=4)


if __name__ == "__main__":
    address = Address()
    print(address.generate())