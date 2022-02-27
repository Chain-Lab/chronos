import binascii
import copy
import hashlib
import json

import ecdsa

PUB_KEY = "89cd9047140ab2fe45f25b141ff451a2182836bf3f3346cddfe129c703e902359f0f180c5646a547d932dbfcbf03d0aa21b181dc6c86e4b5dfa952c8d5e0457b"
ADDRESS = "1PuRN6PvTfhVazxoK8zZ3eFvTUSU76VHRF"
PRV_KEY = "9beb4bdbe87c931b0517877819384b79847c2918ba575fa495f907aed4d77d0a"


def sum256_hex(*args):
    m = hashlib.sha256()
    for arg in args:
        if isinstance(arg, str):
            m.update(arg.encode())
        else:
            m.update(arg)
    return m.hexdigest()


def get_transaction_hash(inputs, outputs):
    data_list = [str(input_tx) for input_tx in inputs]
    vouts_list = [str(output) for output in outputs]
    data_list.extend(vouts_list)
    data = ''.join(data_list)
    print(data)
    hash = sum256_hex(data)
    return hash


def raw_transaction(inputs, amount, address, total):
    transaction = {
        "inputs": [],
        "outputs": [],
        "tx_hash": ""
    }

    for input_tx in inputs:
        transaction["inputs"].append(
            {
                "tx_hash": input_tx["tx_hash"],
                "index": input_tx["index"],
                "signature": None,
                "pub_key": PUB_KEY,
                "vote_info": {}
            }
        )

    transaction["outputs"].append(
        {
            "value": amount,
            "pub_key_hash": address
        }
    )
    if total - amount > 0:
        transaction["outputs"].append(
            {
                "value": total - amount,
                "pub_key_hash": ADDRESS
            }
        )

    transaction["tx_hash"] = get_transaction_hash(transaction["inputs"], transaction["outputs"])
    return transaction


def sign_transaction(raw_tx: dict):
    tx_copy = copy.deepcopy(raw_tx)

    for idx, input_tx in enumerate(raw_tx["inputs"]):
        tx_copy["inputs"][idx]["signature"] = None
        tx_copy["inputs"][idx]["pub_key"] = "1PuRN6PvTfhVazxoK8zZ3eFvTUSU76VHRF"
        tx_copy["tx_hash"] = get_transaction_hash(tx_copy["inputs"], tx_copy["outputs"])
        print(tx_copy, tx_copy["tx_hash"])
        tx_copy["inputs"][idx]["pub_key"] = None


        sk = ecdsa.SigningKey.from_string(binascii.a2b_hex(PRV_KEY), curve=ecdsa.SECP256k1)
        sign = sk.sign(tx_copy["tx_hash"].encode())
        raw_tx["inputs"][idx]["signature"] = binascii.b2a_hex(sign).decode()

    return raw_tx


if __name__ == "__main__":
    inputs = [
        {
            "index": 0,
            "output": {
                "index": 0,
                "pub_key_hash": "1PuRN6PvTfhVazxoK8zZ3eFvTUSU76VHRF",
                "value": 10
            },
            "tx_hash": "29c79a73819ac5dcd8c5d83a27743d44e026ccd3ae175b38e1fa1447196988a5"
        }
    ]
    raw_tx = raw_transaction(inputs, 5, "1DGA4UvmUmmkyjgdxe88BbYWQUTgCw7Cai", 10)
    signed_tx = sign_transaction(raw_tx)
    print(json.dumps(signed_tx))