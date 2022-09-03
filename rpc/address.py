import json
import logging

from core.utxo import UTXOSet
from rpc.grpcs import address_pb2
from rpc.grpcs import address_pb2_grpc


class AddressService(address_pb2_grpc.AddressServicer):
    def get_address_utxo(self, request, context):
        address = request.address

        if address is None:
            logging.error("RPC receive error address.")

        utxo_set = UTXOSet()

        result = utxo_set.find_utxo(address)
        utxo: dict

        for key in result:
            if "_id" in result[key]["output"]:
                result[key]["output"].pop("_id")
            if "_rev" in result[key]["output"]:
                result[key]["output"].pop("_rev")

        return address_pb2.UtxoRespond(utxos=json.dumps(result))


