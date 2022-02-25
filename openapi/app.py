import threading

from flask import Flask

from core.config import Config
from openapi.transaction import transaction_blueprint


def server():
    """
    flask的rust接口服务， 首先注册子模块蓝图再开线程
    """
    app = Flask(__name__)
    app.register_blueprint(transaction_blueprint)

    thread = threading.Thread(target=app.run, args=("0.0.0.0", ))
    thread.start()
