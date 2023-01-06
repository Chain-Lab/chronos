import binascii
import logging.config
import os
import socket
import random
import time

import yappi
import couchdb
import fire
import yaml
from ecdsa import SigningKey, SECP256k1

import core
import node
import utils
import threads
import rpc as rrpc

from core.block_chain import BlockChain
from core.config import Config
from core.transaction import Transaction
from core.utxo import UTXOSet
from node import client
from node.gossip import Gossip
from node.peer import Peer
from node.peer_to_peer import P2p
from node.server import Server
from node.manager import Manager
from utils import funcs
from utils.b58code import Base58Code
from utils import number_theory
from rpc.rpcserver import RPCServer

"""
注意： 该文件仅用于测试
"""


def setup_logger(default_path="logging.yml", default_level=logging.DEBUG, env_key="LOG_CFG"):
    path = default_path
    value = os.getenv(env_key, None)
    if value:
        path = value

    if os.path.exists(path):
        current_time = time.strftime("%Y%m%d%H%M", time.localtime(time.time()))
        with open(path, "r", encoding='utf-8') as f:
            config = yaml.full_load(f)
            config["handlers"]["file"]["filename"] = "chronos-" + current_time + ".log"
            logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)


def run():
    setup_logger()
    try:
        yappi.set_clock_type("wall")
        yappi.start()

        bc = BlockChain()
        utxo_set = UTXOSet()
        utxo_set.reindex(bc)
        logging.info("UTXO set reindex finish")

        gossip = Gossip()
        gossip.run()

        tcpserver = Server()
        tcpserver.listen()
        tcpserver.run()
        logging.info("TCP Server start running")

        rpc = RPCServer()
        rpc.start()
        logging.info("RPC server start")

        p2p = P2p()
        server = Peer(Manager())
        server.run(p2p)
        p2p.run()
    except KeyboardInterrupt:
        with open("./func_stats.ya", "w") as f:
            yappi.get_func_stats(filter_callback=lambda x: yappi.module_matches(x, [
                core.block_chain, core.utxo, core.transaction, core.txmempool,
                node.server, node.client, node.gossip,
                threads.selector, threads.calculator,
                utils.leveldb, utils.network,
                rrpc.node, rrpc.block, rrpc.address, rrpc.transaction
            ])).sort("ttot", "desc").print_all(f)
            # yappi.get_func_stats().sort("ttot", "desc").print_all(f)
        with open("./thread_stats.ya", "w") as f:
            yappi.get_thread_stats().print_all(f)

def genesis():
    p = number_theory.get_prime(512)
    q = number_theory.get_prime(512)
    n = p * q
    t = 10000000

    delay_params = {
        "order": binascii.b2a_hex(n.to_bytes(
            length=(n.bit_length() + 7) // 8,
            byteorder='big',
            signed=False
        )).decode(),
        "time_param": t,
        # 在目前开发过程中设置为默认的256位随机数
        "seed": funcs.int2hex(number_theory.get_prime(256)),
        # 用于验证的参数， 节点计算的同时计算proof
        "verify_param": funcs.int2hex(number_theory.get_prime(256))
    }
    logging.debug(delay_params)

    bc = BlockChain()
    tx = Transaction.coinbase_tx({}, delay_params)
    bc.new_genesis_block(tx)


def init():
    """
    配置文件初始化命令
    !!! 注意：不保存私钥， 仅用于测试
    :return:
    """
    # 生成随机节点id
    node_id = random.randint(2, 100)

    # 生成本地密钥对
    sign_key = SigningKey.generate(curve=SECP256k1)
    public_key = sign_key.get_verifying_key()

    private_address = b'\0' + funcs.hash_public_key(public_key.to_string())
    address = Base58Code.encode_check(private_address).decode()

    public_key = binascii.b2a_hex(public_key.to_string()).decode()

    # 获取网卡ip地址（仅针对云服务器进行使用）
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip_address = s.getsockname()[0]
    s.close()

    Config().set("node.address", address)
    Config().set("node.public_key", public_key)
    Config().set("node.listen_ip", ip_address)
    Config().set("node.id", str(node_id))
    Config().set("node.is_bootstrap", str(0))
    Config().save()


def clear():
    db_url = Config().get("database.url")
    db = couchdb.Server(db_url)
    db.delete('block_chain1')


def get_tx_data(height):
    bc = BlockChain()
    heights = []
    result = []
    total = 0

    for i in range(height):
        block = bc.get_block_by_height(i)
        heights.append(i)
        result.append(len(block.transactions))
        total += len(block.transactions)

    print("heights: ", heights)
    print("result:", result)
    print("total: {}".format(total))

def get_tx(hash):
    bc = BlockChain()
    transaction = bc.get_transaction_by_tx_hash(hash)
    print(transaction.outputs)


def get_timestamp(height):
    bc = BlockChain()
    heights = []
    result = []

    block = bc.get_block_by_height(0)
    timestamp = int(block.block_header.timestamp)

    for i in range(1, height, 1):
        block = bc.get_block_by_height(i)
        heights.append(i)
        result.append((int(block.block_header.timestamp) - timestamp) / 1000)
        timestamp = int(block.block_header.timestamp)

    print("heights: ", height)
    print("result:", result)

def calculate_tx_size():
    setup_logger()
    bc = BlockChain()
    block = bc.get_block_by_height(200)
    transactions = block.transactions
    tx = transactions[0]
    tx_body = tx.serialize()
    # 1264 bytes
    logging.info("Transaction size: {}".format(tx_body, 'utf-8').__sizeof__())


if __name__ == "__main__":
    fire.Fire({
        'run': run,
        'genesis': genesis,
        'init': init,
        'get_tx_data': get_tx_data,
        'get_timestamp': get_timestamp,
        'clear': clear
    })
