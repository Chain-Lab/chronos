from flask import request
from flask import Blueprint
from flask import jsonify

from openapi.statuscode import STATUS
from core.utxo import UTXOSet

address_blueprint = Blueprint("address", __name__, url_prefix="/address")


@address_blueprint.route("/utxos", methods=["GET"])
def utxos():
    address = request.args.get("address", None)

    if address is None:
        return "Params is invalid", STATUS.BAD_REQUEST

    utxo_set = UTXOSet()
    result = utxo_set.find_utxo(address)
    utxo: dict

    # todo: 清除查询到的_id, _rev, 应该可以在query中进行返回信息配置
    for utxo in result:
        utxo["output"].pop("_id")
        utxo["output"].pop("_rev")

    return jsonify(result), STATUS.OK