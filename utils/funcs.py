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


def pub_to_address(s: str):
    '''
    公钥转地址
    :param s: 公钥字符串
    :return:
    '''
    return b58code.Base58Code.encode_check(b'\0' + hash_public_key(bytes.fromhex(s))).decode()


def shared_prefix(a: bytes, b:bytes):
    a = int(a.hex(), 16)
    b = int(b.hex(), 16)
    result = 160
    a ^= b

    while a > 0:
        result -= 1
        a >>= 1

    return result

