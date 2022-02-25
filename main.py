import os
import threading

import yaml

import fire
import logging.config
# from flask import Flask

from core.block_chain import BlockChain
from core.utxo import UTXOSet
from core.transaction import Transaction
from core.config import Config
from node.server import Server
from node.peer_to_peer import P2p
from node.peer import Peer
from utils.dbutil import DBUtil
# from openapi.transaction import transaction_blueprint


def setup_logger(default_path="logging.yaml", default_level=logging.DEBUG, env_key="LOG_CFG"):
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
    logging.info("UTXO set reindex finish...")

    tcpserver = Server()
    tcpserver.listen()
    tcpserver.run()
    logging.info("TCP Server start running...")

    p2p = P2p()
    thread = threading.Thread(target=p2p.task)
    thread.start()
    logging.info("P2P Server start running...")
    thread.join()

    # app = Flask(__name__)
    # app.register_blueprint(transaction_blueprint)
    # app.run()


def genesis():
    bc = BlockChain()
    tx = Transaction.coinbase_tx({})
    bc.new_genesis_block(tx)


def db_test(key):
    db = DBUtil(Config().get('database.url'))
    print(db.get(key))


if __name__ == "__main__":
    fire.Fire()
