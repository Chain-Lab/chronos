import json
import logging

from rpc.grpc import address_pb2
from rpc.grpc import address_pb2_grpc
from core.utxo import UTXOSet


class AddressService(address_pb2_grpc.AddressServicer):
    def get_address_utxo(self, request, context):
        address = request.address

        if address is None:
            logging.error("RPC receive error address.")

        utxo_set = UTXOSet()

        result = utxo_set.find_utxo(address)
        utxo: dict

        for utxo in result:
            utxo["output"].pop("_id")
            utxo["output"].pop("_rev")

        return address_pb2.UtxoRespond(utxos=json.dumps(result))
