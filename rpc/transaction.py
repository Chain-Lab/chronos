import json

from rpc.grpcs import transaction_pb2
from rpc.grpcs import transaction_pb2_grpc
from utils.validator import json_validator
from core.transaction import Transaction
from core.block_chain import BlockChain
from node.peer import Peer


class TransactionService(transaction_pb2_grpc.TransactionServicer):
    def submit_transaction(self, request, context):
        transaction = request.signedTransaction
        signed_dict = json.loads(transaction)
        is_valid = json_validator("./schemas/transaction.json", signed_dict)

        assert is_valid is True

        transaction = Transaction.deserialize(signed_dict)
        bc = BlockChain()

        assert bc.verify_transaction(transaction) is True

        peer = Peer()
        peer.broadcast(transaction)

        return transaction_pb2.SubmitTransactionRespond(status=0)

    def get_transaction(self, request, context):
        tx_hash = request.hash

        bc = BlockChain()
        transaction = bc.get_transaction_by_tx_hash(tx_hash)

        tx_dict = transaction.serialize()

        return transaction_pb2.GetTransactionRespond(status=0, transaction=json.dumps(tx_dict))
