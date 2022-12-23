import json

from core.block_chain import BlockChain
from core.transaction import Transaction
from node.gossip import Gossip
from rpc.grpcs import transaction_pb2
from rpc.grpcs import transaction_pb2_grpc
from utils.validator import json_validator
from utils.locks import package_lock


class TransactionService(transaction_pb2_grpc.TransactionServicer):
    def submit_transaction(self, request, context):
        transaction = request.signedTransaction
        signed_dict = json.loads(transaction)

        # 格式校验
        is_valid = json_validator("./schemas/transaction.json", signed_dict)

        assert is_valid is True

        transaction = Transaction.deserialize(signed_dict)
        bc = BlockChain()

        # if not bc.verify_transaction(transaction):
        #     return transaction_pb2.SubmitTransactionRespond(status=-1)
        # peer = Peer()
        # peer.broadcast(transaction)
        if package_lock.locked():
            return transaction_pb2.SubmitTransactionRespond(status=0)

        Gossip().append(transaction)

        return transaction_pb2.SubmitTransactionRespond(status=0)

    def get_transaction(self, request, context):
        tx_hash = request.hash

        bc = BlockChain()
        is_in_cache = bc.is_transaction_in_cache(tx_hash)
        if not is_in_cache:
            return transaction_pb2.GetTransactionRespond(status=-1, transaction="")

        return transaction_pb2.GetTransactionRespond(status=0, transaction="")
