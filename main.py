import binascii
import os
import threading

import yaml

import fire
import socket
import logging.config
# from flask import Flask

from openapi import app
from core.block_chain import BlockChain
from core.utxo import UTXOSet
from core.transaction import Transaction
from core.config import Config
from node.server import Server
from node.peer_to_peer import P2p
from node.peer import Peer
from utils.dbutil import DBUtil
from utils import funcs
from utils.b58code import Base58Code
from ecdsa import SigningKey, SECP256k1
# from openapi.transaction import transaction_blueprint

"""
注意： 该文件仅用于测试
"""


def setup_logger(default_path="logging.yml", default_level=logging.DEBUG, env_key="LOG_CFG"):
    path = default_path
    value = os.getenv(env_key, None)
    if value:
        path = value

    if os.path.exists(path):
        with open(path, "r") as f:
            config = yaml.full_load(f)
            logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)


def run():
    setup_logger()

    bc = BlockChain()
    utxo_set = UTXOSet()
    utxo_set.reindex(bc)
    logging.info("UTXO set reindex finish")

    tcpserver = Server()
    tcpserver.listen()
    tcpserver.run()
    logging.info("TCP Server start running")

    app.server()
    logging.info("Falsk restful openapi start")

    p2p = P2p()
    server = Peer()
    server.run(p2p)
    p2p.run()


def genesis():
    bc = BlockChain()
    tx = Transaction.coinbase_tx({})
    bc.new_genesis_block(tx)


def init(node_id):
    """
    配置文件初始化命令
    !!! 注意：不保存私钥， 仅用于测试
    :return:
    """
    sign_key = SigningKey.generate(curve=SECP256k1)
    public_key = sign_key.get_verifying_key()

    private_address = b'\0' + funcs.hash_public_key(public_key.to_string())
    address = Base58Code.encode_check(private_address).decode()

    public_key = binascii.b2a_hex(public_key.to_string()).decode()

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip_address = s.getsockname()[0]
    s.close()

    Config().set("node.address", address)
    Config().set("node.pub_key", public_key)
    Config().set("node.listen_ip", ip_address)
    Config().set("node.id", str(node_id))
    Config().save()


def db_test(key):
    db = DBUtil(Config().get('database.url'))
    print(db.get(key))


if __name__ == "__main__":
    fire.Fire()
