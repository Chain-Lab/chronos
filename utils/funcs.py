import binascii
import hashlib

from utils import b58code


def hash_public_key(pubkey):
    ripemd160 = hashlib.new('ripemd160')
    ripemd160.update(hashlib.sha256(pubkey).digest())
    return ripemd160.digest()


def address_to_pubkey_hash(address):
    return b58code.Base58Code.decode_check(address)[1:]


def sum256_byte(*args):
    m = hashlib.sha256()
    for arg in args:
        if isinstance(arg, str):
            m.update(arg.encode())
        else:
            m.update(arg)
    return m.digest()


def sum256_hex(*args):
    """
    对数据进行sha256哈希
    :return: 16进制格式的哈希字符串
    """
    m = hashlib.sha256()
    for arg in args:
        if isinstance(arg, str):
            m.update(arg.encode())
        else:
            m.update(arg)
    return m.hexdigest()


def int2hex(value: int):
    if value is None:
        value = 0

    bit_length = value.bit_length()
    return binascii.b2a_hex(value.to_bytes(length=(bit_length + 7) // 8, byteorder='big', signed=False)).decode()


def hex2int(s: str):
    if s is None:
        return 0
    return int.from_bytes(bytes.fromhex(s), byteorder='big')
