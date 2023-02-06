import json
import logging

from core.utxo import UTXOSet
from rpc.grpcs import address_pb2
from rpc.grpcs import address_pb2_grpc


class AddressService(address_pb2_grpc.AddressServicer):
    def get_address_utxo(self, request, context):
        return address_pb2.UtxoRespond("null")
        # address = request.address
        #
        # if address is None:
        #     logging.error("RPC receive error address.")
        #
        # utxo_set = UTXOSet()
        #
        # result = utxo_set.find_utxo(address)
        # utxo: dict
        #
        # return address_pb2.UtxoRespond(utxos=json.dumps(result))


