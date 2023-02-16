import copy
import json
import logging
import socket
import threading
import time

from core.block import Block
from core.block_chain import BlockChain
from core.config import Config
from core.txmempool import TxMemPool
from node.constants import STATUS
from node.message import Message
from node.timer import Timer
from node.manager import Manager
from threads.calculator import Calculator
from utils.locks import package_lock, package_cond
from utils.network import TCPConnect

from utils import constant


class Server(object):
    def __init__(self, ip: str = None, port: int = None):
        """
        由cli调用时传入ip和端口来进行初始化， 尽量保证模块独立
        :param ip: ip地址，一般为localhost
        :param port: 端口
        """
        if ip is None and port is None:
            ip = Config().get('node.listen_ip')
            port = int(Config().get('node.listen_port'))
        self.sock = socket.socket()
        self.ip = ip
        self.port = port
        # 本地未发送的交易， 逻辑已经移动到Gossip协议
        # self.txs = []
        self.tx_pool = TxMemPool()

        # 单独线程的内存空间， 各线程独立
        self.thread_local = threading.local()

    def listen(self):
        """
        监听端口， 绑定ip和端口
        :return: None
        """
        self.sock.bind((self.ip, self.port))
        self.sock.listen(10)

    def listen_loop(self):
        """
        监听循环， 监听到连接则开一个线程进行处理
        :return: None
        """
        while True:
            # todo： conn后的逻辑分到另外一个类， 这里应该是一个sock池管理的地方
            #  可以便于每个实例之间的变量独立， 这样就可以不再使用threading.local()来处理不同线程的参数
            conn, address = self.sock.accept()
            thread = threading.Thread(target=self.handle_loop, args=(conn, address))
            thread.start()

    def run(self):
        """
        类的运行函数， 开一个线程进行监听, 同时启动VDF的计算
        :return: None
        """
        calculator = Calculator()
        calculator.run()
        # 实例化timer， 进行初始化操作
        Timer()

        thread = threading.Thread(target=self.listen_loop, args=())
        thread.start()

    def handle_loop(self, conn, address):
        """
        处理client信息的循环， 接收消息并返回信息
        :param conn: 与client的socket连接
        :param address:
        :return: None
        """
        # 设置线程名， 便于Debug
        thread_obj = threading.current_thread()
        thread_obj.name = "Server Thread - " + thread_obj.getName().split("-")[-1]
        rec_msg = None
        server_continue = True

        while True:
            with package_cond:
                while package_lock.locked():
                    logging.debug("Wait block package finished.")
                    package_cond.wait()

            try:
                rec_data = TCPConnect.recv_msg(conn)
                if rec_data is None:
                    conn.close()
                    break

                rec_msg = json.loads(rec_data.decode('utf-8'))

            except ValueError:
                try:
                    TCPConnect.send_msg(conn, '{"code": 0, "data": ""}')
                except BrokenPipeError:
                    logging.info("Client lost connect, close server.")
                    server_continue = False

            if rec_msg is not None:

                try:
                    send_data = self.handle(rec_msg)
                # 先直接使用except保证节点程序在遇到异常时能够正常进行处理
                except:
                    continue

                try:
                    TCPConnect.send_msg(conn, send_data)
                except BrokenPipeError:
                    logging.info("Client lost connect, close server.")
                    server_continue = False
            if server_continue:
                pass
            else:
                conn.close()
                break

    def handle(self, message: dict):
        """
        :param message: 从client接收到的待处理的message
        :return: 消息处理完成后应该返回的数据
        """
        code = message.get('code', 0)
        if code == STATUS.HANDSHAKE:
            result_message = self.handle_handshake(message)
        elif code == STATUS.PULL_BLOCK:
            result_message = self.handle_pull_block(message)
        elif code == STATUS.NEW_BLOCK:
            result_message = self.handle_new_block(message)
        elif code == STATUS.NEW_BLOCK_HASH:
            result_message = self.handle_new_block_hash(message)
        else:
            result_message = Message.empty_message()
        return json.dumps(result_message.__dict__)

    def handle_handshake(self, message: dict):
        """
        状态码STATUS.HAND_SHAKE_MSG = 1， 处理握手请求
        主要进行本地和远程的区块信息更新
        :param message:
        :return:
        """
        data = message.get("data", {})
        remote_height = data.get("height", -1)

        bc = BlockChain()
        block, prev_hash = bc.get_latest_block()

        result_data = {
            "height": -1,
            "address": Config().get('node.address'),
            "timestamp": time.time(),
        }

        if not block:
            block, _ = bc.get_latest_block()

        try:
            result_data['height'] = block.block_header.height
        except AttributeError:
            result_data['height'] = -1

        result = Message(STATUS.HANDSHAKE, result_data)
        return result

    def handle_pull_block(self, message: dict):
        """
        状态码 STATUS.PULL_BLOCK, 发送对应高度的区块给对端 Client
        Args:
            message: 包含区块高度的消息
        """
        height = message.get("data", -1)
        # logging.info("Receive pull block request, send block #{}.".format(height))
        bc = BlockChain()
        block = bc.get_block_by_height(height)
        try:
            result_data = block.serialize()
        except AttributeError:
            result = Message.empty_message()
        else:
            result = Message(STATUS.PUSH_BLOCK, result_data)
        return result

    def handle_new_block(self, message: dict):
        """
        状态码 STATUS.NEW_BLOCK， 将新区块添加到 Manager 中进行广播
        """
        data = message.get('data', {})
        block = Block.deserialize(data)
        Manager().append_block(block)
        return Message.empty_message()

    def handle_new_block_hash(self, message: dict):
        """
        状态码 STATUS_NEW_BLOCK_HASH， 对新的区块哈希值进行响应
        """
        block_hash = message.get("data", None)
        if not block_hash:
            return Message.empty_message()

        if Manager().is_known_block(block_hash):
            return Message(STATUS.BLOCK_KNOWN, {})
        else:
            return Message(STATUS.GET_BLOCK, block_hash)
