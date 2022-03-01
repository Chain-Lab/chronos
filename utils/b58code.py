from hashlib import sha256

from utils.decorators import scrub_base58_input


class Base58Code(object):
    alphabet = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

    # python2
    if bytes == str:
        iseq, bseq, buffer = (
            lambda s: map(ord, s),
            lambda s: ''.join(map(chr, s)),
            lambda s: s,
        )
    # python3
    else:
        iseq, bseq, buffer = (
            lambda s: s,
            bytes,
            lambda s: s.buffer,
        )

    # 对整数进行base58编码和解码
    @staticmethod
    def encode_int(i: int, default_one: bool = True):
        """
        :param i: int型, 需要进行编码的整数
        :param default_one: bool型, 是否需要进行编码
        :return: 返回编码后得到的bytes类型编码
        """
        if not i and default_one:
            return Base58Code.alphabet[0: 1]
        string = b""
        while i:
            i, idx = divmod(i, 58)
            string = Base58Code.alphabet[idx: idx + 1] + string
        return string

    @staticmethod
    @scrub_base58_input
    def decode_int(v: bytes):
        """
        :param v: bytes型, 传入需要解码的数据
        :return: int型, 返回编码后得到的int型数据
        """
        dec = 0
        for c in v:
            dec = dec * 58 + Base58Code.alphabet.index(c)
        return dec

    # 对字符串进行base58编码和解码
    @staticmethod
    @scrub_base58_input
    def encode(v: bytes):
        """
        :param v: bytes型, 传入前经过装饰器进行数据类型确认
        :return: bytes型, 编码后得到的数据
        """
        nPad = len(v)
        v = v.lstrip(b'\0')
        nPad -= len(v)

        p, acc = 1, 0
        for c in Base58Code.iseq(reversed(v)):
            acc += p * c
            p = p << 8

        result = Base58Code.encode_int(acc, default_one=False)
        return Base58Code.alphabet[0: 1] * nPad + result

    @staticmethod
    @scrub_base58_input
    def decode(v: bytes):
        """
        :param v: bytes型, 经过修饰器进行了类型转换
        :return: bytes型, 返回解码的数据
        """
        origin_len = len(v)
        v = v.lstrip(Base58Code.alphabet[0: 1])
        new_len = len(v)

        acc = Base58Code.decode_int(v)

        result = []
        while acc > 0:
            acc, mod = divmod(acc, 256)
            result.append(mod)

        return b'\0' * (origin_len - new_len) + Base58Code.bseq(reversed(result))

    # base58check
    @staticmethod
    @scrub_base58_input
    def encode_check(v: bytes):
        """
        带有数据校验的base58编码, 用于检查输入是否存在错误
        :param v: bytes型, 经过了修饰器进行数据检查
        :return: bytes型, 输出的编码数据
        """
        digest = sha256(sha256(v).digest()).digest()
        return Base58Code.encode(v + digest[:4])

    @staticmethod
    def decode_check(v: bytes):
        """
        带有数据校验的base58解码, 可以确认编码是否存在错误
        :param v: bytes型, 经过修饰器进行数据检查
        :return: bytes型, 输出的解码数据
        """
        result = Base58Code.decode(v)
        result, check = result[:-4], result[-4:]
        digest = sha256(sha256(result).digest()).digest()

        if check != digest[:4]:
            raise ValueError("Invalid checksum")

        return result


if __name__ == "__main__":
    print(Base58Code.encode("2334234234"))
