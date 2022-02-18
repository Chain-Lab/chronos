from core.blockchain import BlockChain
from core.utxo import UTXOSet
from node.client import Client
from node.server import Server
from node.peer_to_peer import P2p

if __name__ == "__main__":
    bc = BlockChain()
    utxo_set = UTXOSet()
    utxo_set.reindex(bc)

    server = Server()


