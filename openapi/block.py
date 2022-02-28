import logging

from flask import Blueprint
from flask import request

from openapi.statuscode import STATUS
from core.block_chain import BlockChain

block_blueprint = Blueprint("block", __name__, url_prefix="/block")


@block_blueprint.route("/height/<height>", methods=["GET"])
def get_block_by_height(height):
    assert height == request.view_args.get("height", None)

    logging.info("Receive request block #{}".format(height))
    try:
        height = int(height)
    except ValueError:
        return "Height param error.", STATUS.BAD_REQUEST

    bc = BlockChain()
    block = bc.get_block_by_height(height)

    if block:
        return block.serialize(), STATUS.OK
    else:
        return "Block is not exists.", STATUS.NOT_FOUNT


@block_blueprint.route("/hash/<hash>", methods=["GET"])
def get_block_by_hash(hash):
    assert hash == request.view_args.get("hash", None)

    logging.info("Receive request block #{}".format(hash))
    bc = BlockChain()
    block = bc.get_block_by_hash(hash)

    if block:
        return block.serialize(), STATUS.OK
    else:
        return "Block is not exists.", STATUS.NOT_FOUNT


@block_blueprint.route("/latest", methods=["GET"])
def get_latest_block():

    bc = BlockChain()
    block, _ = bc.get_latest_block()

    if block:
        return block.serialize(), STATUS.OK
    else:
        return "Block is not exists.", STATUS.NOT_FOUNT
