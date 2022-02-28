import logging

from flask import Blueprint
from flask import request

from core.block_chain import BlockChain
from core.transaction import Transaction
from node.peer import Peer
from openapi.statuscode import STATUS

transaction_blueprint = Blueprint("transaction", __name__, url_prefix="/transaction")


@transaction_blueprint.route("/submit", methods=["POST"])
def submit():
    transaction_json = request.get_json()
    transaction = Transaction.deserialize(transaction_json)

    logging.debug(transaction.inputs)

    if transaction is None:
        return "Transaction data is invalid", STATUS.BAD_REQUEST

    bc = BlockChain()
    if not bc.verify_transaction(transaction):
        logging.warning("Receive transaction is invalid")
        return 'Transaction verify failed', STATUS.BAD_REQUEST

    peer = Peer()
    peer.broadcast(transaction)

    return 'Transaction submitted', STATUS.ACCEPTED


@transaction_blueprint.route("/hash/<tx_hash>", methods=["GET"])
def get_transaction_by_hash(tx_hash):
    assert tx_hash == request.view_args.get("tx_hash", None)

    logging.info("Receive openapi request transaction {}".format(tx_hash))

    bc = BlockChain()
    transaction = bc.get_transaction_by_tx_hash(tx_hash)

    if transaction:
        return transaction.serialize(), STATUS.OK
    else:
        return "Transaction is not existed", STATUS.BAD_REQUEST