import binascii
import json

from ecdsa import SigningKey, SECP256k1

from utils import funcs
from utils.b58code import Base58Code

"""
用于进行性能测试生成钱包的代码
批量生成指令数量的代码，并且生成对应的转账代码
"""


def generate():
    sign_key = SigningKey.generate(curve=SECP256k1)
    private_key = sign_key
    public_key = sign_key.get_verifying_key()

    private_address = b'\0' + funcs.hash_public_key(public_key.to_string())
    address = Base58Code.encode_check(private_address).decode()

    result = {
        "prv": binascii.b2a_hex(private_key.to_string()).decode(),
        "pub": binascii.b2a_hex(public_key.to_string()).decode(),
        "address": address
    }
    return result


if __name__ == "__main__":
    with open("wallets.json", 'w') as f:
        wallets = []
        for _ in range(200):
            wallet = generate()
            wallets.append(wallet)
        f.write(json.dumps(wallets))
