import fire

from core.block_chain import BlockChain
from core.utxo import UTXOSet
from core.transaction import Transaction
from core.config import Config
from node.server import Server
from node.peer_to_peer import P2p
from node.peer import Peer
from utils.dbutil import DBUtil


def run():
    bc = BlockChain()
    utxo_set = UTXOSet()
    utxo_set.reindex(bc)

    tcpserver = Server()
    tcpserver.listen()
    tcpserver.run()

    p2p = P2p()
    server = Peer()
    server.run(p2p)
    p2p.run()


def genesis():
    bc = BlockChain()
    tx = Transaction.coinbase_tx({})
    bc.new_genesis_block(tx)


def db_test(key):
    db = DBUtil(Config().get('database.url'))
    print(db.get(key))


if __name__ == "__main__":
    fire.Fire()
