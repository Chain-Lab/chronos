from flask import Blueprint
from flask import jsonify
from flask import request

from core.utxo import UTXOSet
from openapi.constant import VERSION
from openapi.statuscode import STATUS

address_blueprint = Blueprint("address", __name__, url_prefix="/{}/address".format(VERSION))


@address_blueprint.route("/utxos/<address>", methods=["GET"])
def utxos(address):
    """
    通过地址拉取utxo的接口， 调用Utxoset的方法进行查询
    返回json数据
    :param address: 待查询的address
    :return: 返回json数据， 200状态码
    """
    assert address == request.view_args.get("address", None)

    if address is None:
        return "Params is invalid", STATUS.BAD_REQUEST

    utxo_set = UTXOSet()
    result = utxo_set.find_utxo(address)
    utxo: dict

    for utxo in result:
        utxo["output"].pop("_id")
        utxo["output"].pop("_rev")

    return jsonify(result), STATUS.OK
