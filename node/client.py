import copy
import json
import logging
import queue
import socket
import threading
import time

from lru import LRU

from core.block import Block
from core.block_chain import BlockChain
from core.config import Config
from core.txmempool import TxMemPool
from node.constants import STATUS
from node.message import Message
from node.timer import Timer
from threads.calculator import Calculator
from utils.leveldb import LevelDB
from utils.locks import package_lock, package_cond
from utils.network import TCPConnect


class Client(object):
    # Client线程类， 多个client之间相互独立， 不共享变量
    def __init__(self, ip, port, manager):
        self.sock = socket.socket()

        self.sock.connect((ip, port))
        logging.info("Connect to server ip: {} port: {}".format(ip, port))

        # 交易池， 单例
        self.tx_pool = TxMemPool()

        # 本地的钱包地址
        self.local_address = Config().get('node.address')

        # 最新打包区块的数据
        self.new_block = None

        self.__manager = manager

        self.__queued_blocks = queue.Queue()

        self.__queued_block_anns = queue.Queue()

        # 已知区块信息的区块，暂未使用
        self.__known_blocks = LRU(500)

    def send(self, message):
        """
        发送信息给邻居节点， 在出现Broke异常的情况下说明连接断开
        :param message: 待发送信息
        """
        # 解析得到接收的消息的数据
        rec_message = None
        data = json.dumps(message.__dict__)

        # 尝试发送数据，如果数据发送出现错误则说明链接存在问题，关闭链接
        try:
            # self.sock.sendall(data.encode())
            TCPConnect.send_msg(self.sock, data)
        except BrokenPipeError:
            logging.info("Lost connect, client close.")
            return True

        try:
            # 接收server的数据
            # rec_data = self.sock.recv(4096 * 2)
            rec_data = TCPConnect.recv_msg(self.sock)
            if rec_data is None:
                logging.debug("Receive data is empty")
                return True
            rec_message = json.loads(rec_data.decode('utf-8'))

            data = rec_message.get('data', '')

            if isinstance(data, dict):
                address = data.get('address', '')
                if address != "":
                    db = LevelDB()
                    old_wallets = db.get('wallets')

                    if old_wallets is None:
                        logging.info('Remote node wallet is not created in database, create new record.')
                        db.insert('wallets', {})
                        old_wallets = db.get('wallets')
                    old_wallets.update({
                        address: {
                            'time': data.get('time', ''),
                            'id': int(Config().get('node.id'))
                        }
                    })
                    db.insert("wallets", old_wallets)
        # 在信息错误或连接断开时会产生该错误
        except json.decoder.JSONDecodeError as e:
            logging.debug(data)
            logging.error(e)
        except ConnectionResetError:
            return True

        if rec_message is not None:
            try:
                self.handle(rec_message)
            # 在出现异常的情况下不断开连接， 保证线程能够正常运行， 对于具体异常的处理待完成
            except:
                return False

        return False

    def shake_loop(self):
        """
        握手循环， 如果存在交易的情况下就发送交易
        :return:
        """
        # 设置线程名， 便于输出日志debug
        thread_obj = threading.current_thread()
        thread_obj.name = "Client Thread - " + thread_obj.getName().split("-")[-1]

        bc = BlockChain()

        while True:
            # 在本地进行打包区块时让出cpu资源
            with package_cond:
                while package_lock.locked():
                    logging.debug("Wait block package finished.")
                    package_cond.wait()

            # get_latest_block会返回None导致线程挂掉， 需要catch一下
            try:
                latest_block, prev_hash = bc.get_latest_block()
            except TypeError:
                continue

            # 如果打包了区块， 发送新的区块给对端
            if self.new_block:
                try:
                    self.__manager.append_block(self.new_block)
                except AttributeError:
                    pass

                self.new_block = None

            data = {
                "height": -1,
                "address": Config().get('node.address'),
                "timestamp": time.time(),
            }

            if not latest_block:
                latest_block, _ = bc.get_latest_block()

            if Timer().reach() and Calculator().verify_address(self.local_address) and latest_block:
                height = latest_block.block_header.height
                self.package_new_block(height)
                continue

            if Timer().finish():
                self.__manager.notify_insert()
                continue

            try:
                data['height'] = latest_block.block_header.height
            except AttributeError:
                data['height'] = -1

            if not self.__queued_blocks.empty():
                block = self.__queued_blocks.get()
                send_message = Message(STATUS.NEW_BLOCK, block.serialize())
            elif not self.__queued_block_anns.empty():
                block_hash = self.__queued_block_anns.get()
                send_message = Message(STATUS.NEW_BLOCK_HASH, block_hash)
            else:
                send_message = Message(STATUS.HANDSHAKE, data)
            # logging.debug("Send message: {}".format(data))
            is_closed = self.send(send_message)
            if is_closed:
                self.close()
                break
            # time.sleep(0.01)

    def handle(self, message: dict):
        code = message.get('code', 0)

        if code == STATUS.HANDSHAKE:
            self.handle_handshake(message)
        elif code == STATUS.PUSH_BLOCK:
            self.handle_push_block(message)
        elif code == STATUS.GET_BLOCK:
            self.handle_get_block(message)
        elif code == STATUS.BLOCK_KNOWN:
            self.handle_block_known(message)

    def handle_handshake(self, message: dict):
        """
        状态码为 STATUS.HANDSHAKE = 1, 进行握手操作

        Args:
            message: 待处理的消息
        """
        logging.debug("Receive handshake status code.")
        data = message.get('data', {})
        remote_height = data.get('height', -1)

        bc = BlockChain()
        latest_block, prev_hash = bc.get_latest_block()

        if latest_block:
            local_height = latest_block.block_header.height
        else:
            local_height = -1

        if local_height < remote_height:
            start_height = 0 if local_height == -1 else local_height + 1
            for i in range(start_height, remote_height + 1):
                send_msg = Message(STATUS.PULL_BLOCK, i)
                self.send(send_msg)

    def handle_push_block(self, message: dict):
        """
        状态码为 STATUS.PUSH_BLOCK，从对端拉取到某个确认的区块

        Args:
            message: 包含区块的消息
        """
        data = message.get('data', {})
        block = Block.deserialize(data)
        self.__manager.insert_block(block)

    def handle_get_block(self, message: dict):
        """
        状态码 STATUS.GET_BLOCK, 返回给服务器某个新区块
        """
        block_hash = message.get('data', "")
        block = self.__manager.get_known_block(block_hash)
        send_msg = Message(STATUS.NEW_BLOCK, block.serialize())
        self.send(send_msg)

    def package_new_block(self, height: int):
        if self.tx_pool.packaged:
            logging.debug("Mempool packaged.")
            return

        if package_lock.locked():
            logging.debug("Package locked.")
            return
        package_lock.acquire()
        start_time = time.time()

        logging.info("Lock package lock. Start package memory pool.")
        transactions = self.tx_pool.package(height + 1)
        logging.debug("Package transaction result: {}".format(transactions))

        # 如果取出的交易数据是None， 说明另外一个线程已经打包了， 就不用再管
        # upd: 在新的逻辑里面，不论节点交易池是否存在交易都会进行区块的打包
        if transactions is None:
            logging.debug("Tx memory pool has been packaged.")
            package_lock.release()
            with package_cond:
                package_cond.notify_all()
            return

        bc = BlockChain()
        logging.info("Start package new block.")
        new_block = bc.package_new_block(transactions, {}, Calculator().delay_params)
        self.new_block = copy.deepcopy(new_block)

        if new_block:
            end_time = time.time()
            logging.info("Package block use {}s include count {}".format(end_time - start_time, len(transactions)))
            self.__manager.append_block(new_block)
        else:
            logging.warning("Package failed, rollback txmempool.")
            self.tx_pool.roll_back()

        package_lock.release()

        with package_cond:
            logging.info("Notify all thread.")
            package_cond.notify_all()

        logging.debug("Package new block.")

    def handle_block_known(self, message: dict):
        """
        状态码为 STATUS.BLOCK_KNOWN的响应，在list中添加哈希值
        """
        block_hash = message.get("data")
        self.__known_blocks[block_hash] = self.__manager.get_known_block(block_hash)

    def append_block_queue(self, block):
        self.__queued_blocks.put(block)

    def append_hash_queue(self, block_hash):
        self.__queued_block_anns.put(block_hash)

    def close(self):
        self.sock.close()
