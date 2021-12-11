from hashlib import sha256
from decorators import scrub_base58_input


class b58code(object):

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
    def encode_int(i, default_one=True):
        if not i and default_one:
            return b58code.alphabet[0: 1]
        string = b""
        while i:
            i, idx = divmod(i, 58)
            string = b58code.alphabet[idx: idx + 1] + string
        return string

    @staticmethod
    @scrub_base58_input
    def decode_int(v):
        dec = 0
        for c in v:
            dec = dec * 58 + b58code.alphabet.index(c)
        return dec

    # 对字符串进行base58编码和解码
    @staticmethod
    @scrub_base58_input
    def encode(v):
        nPad = len(v)
        v = v.lstrip(b'\0')
        nPad -= len(v)

        p, acc = 1, 0
        for c in b58code.iseq(reversed(v)):
            acc += p * c
            p = p << 8

        result = b58code.encode_int(acc, default_one=False)
        return b58code.alphabet[0: 1] * nPad + result

    @staticmethod
    @scrub_base58_input
    def decode(v):
        origin_len = len(v)
        v = v.lstrip(b58code.alphabet[0: 1])
        new_len = len(v)

        acc = b58code.decode_int(v)

        result = []
        while acc > 0:
            acc, mod = divmod(acc, 256)
            result.append(mod)

        return b'\0' * (origin_len - new_len) + b58code.bseq(reversed(result))

    # base58check
    @staticmethod
    def encode_check(v):
        digest = sha256(sha256(v).digest()).digest()
        return b58code.encode(v + digest[:4])

    @staticmethod
    def decode_check(v):
        result = b58code.decode(v)
        result, check = result[:-4], result[-4:]
        digest = sha256(sha256(result).digest()).digest()

        if check != digest[:4]:
            raise ValueError("Invalid checksum")

        return result

if __name__ == "__main__":
    print(b58code.encode("2334234234"))