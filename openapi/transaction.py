import logging
from flask import Blueprint
from flask import request
from flask import jsonify

from core.block_chain import BlockChain
from core.transaction import Transaction
from core.utxo import UTXOSet
from node.peer import Peer
from core.config import Config


transaction_blueprint = Blueprint("transaction", __name__, url_prefix="/transaction")


@transaction_blueprint.route("/submit", methods=["POST"])
def submit():
    transaction_json = request.get_json()
    logging.debug("Receive submitted transaction: {}".format(transaction_json))
    transaction = Transaction.deserialize(transaction_json)

    if transaction is None:
        return "Transaction data is invaild", 400

    bc = BlockChain()
    if not bc.verify_transaction(transaction):
        logging.warning("Receive transaction is invalid")
        return 'Transaction verify failed', 400

    peer = Peer()
    peer.broadcast(transaction)
    logging.debug(transaction)

    return 'Transaction submitted', 202


@transaction_blueprint.route("/utxos", methods=["GET"])
def utxos():
    address = request.args.get("address", None)

    if address is None:
        return "Params is invalid", 400

    utxo_set = UTXOSet()
    result = utxo_set.find_utxo(address)

    return jsonify(result), 200