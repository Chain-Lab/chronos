import threading

from flask import Flask

from openapi.address import address_blueprint
from openapi.block import block_blueprint
from openapi.transaction import transaction_blueprint


def server():
    """
    Flask的rust接口服务， 首先注册子模块蓝图再开线程
    """
    app = Flask(__name__)
    # 注册交易相关的蓝图
    app.register_blueprint(transaction_blueprint)
    # 注册地址相关的蓝图
    app.register_blueprint(address_blueprint)
    # 注册区块相关的蓝图
    app.register_blueprint(block_blueprint)

    thread = threading.Thread(target=app.run, args=("0.0.0.0",))
    thread.start()
