from flask import Blueprint
from flask import request

from core.block_chain import BlockChain
from core.transaction import Transaction
from node.peer import Peer
from core.config import Config


transaction_blueprint = Blueprint("transaction", __name__)


@transaction_blueprint.route("/submit")
def submit():
    transaction_json = request.get_json()
    transaction = Transaction.deserialize(transaction_json)
    bc = BlockChain()
    if not bc.verify_transaction(transaction):
        return 'Transaction verify failed', 400

    peer = Peer()
    peer.broadcast(transaction)

    return 'Transaction submitted', 202
