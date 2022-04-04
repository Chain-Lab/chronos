import json
import logging
import socket
import threading
import time

from core.block import Block
from core.block_chain import BlockChain
from core.config import Config
from core.transaction import Transaction
from core.txmempool import TxMemPool
from node.calculator import Calculator
from node.vote_center import VoteCenter
from node.counter import Counter
from node.constants import STATUS
from node.message import Message
from node.timer import Timer
from utils import funcs


class Server(object):
    def __init__(self, ip: str = None, port: int = None):
        """
        由cli调用时传入ip和端口来进行初始化， 尽量保证模块独立
        :param ip: ip地址，一般为localhost
        :param port: 端口
        """
        self.vote_lock = threading.Lock()
        if ip is None and port is None:
            ip = Config().get('node.listen_ip')
            port = int(Config().get('node.listen_port'))
        self.sock = socket.socket()
        self.ip = ip
        self.port = port
        self.txs = []
        self.tx_pool = TxMemPool()
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
        # 连接的client的id
        self.thread_local.client_id = -1
        # client同步标志， 确认是否和所连接的client同步过一次
        self.thread_local.client_synced = False
        # server同步标志， 确认本地投票的信息是否放入到vote_center
        self.thread_local.server_synced = False
        self.thread_local.height = -1

        while True:
            try:
                rec_data = conn.recv(4096 * 2)
                if rec_data == b"":
                    Counter().client_close()
                    conn.close()
                    break

                rec_msg = json.loads(rec_data.decode('utf-8'))

            except ValueError:
                try:
                    # 发送信息， 如果出现错误说明连接断开
                    conn.sendall('{"code": 0, "data": ""}'.encode())
                except BrokenPipeError:
                    logging.info("Client lost connect, close server.")
                    server_continue = False

            if rec_msg is not None:
                send_data = self.handle(rec_msg)
                try:
                    # 发送信息， 如果出现错误说明连接断开
                    conn.sendall(send_data.encode())
                except BrokenPipeError:
                    logging.info("Client lost connect, close server.")
                    server_continue = False
            if server_continue:
                time.sleep(1)
            else:
                # 失去连接， 从vote center中-1
                Counter().client_close()
                conn.close()
                break

    def handle(self, message: dict):
        """
        :param message: 从client接收到的待处理的message
        :return: 消息处理完成后应该返回的数据
        """
        code = message.get('code', 0)
        if code == STATUS.HAND_SHAKE_MSG:
            result_message = self.handle_handshake(message)
        elif code == STATUS.GET_BLOCK_MSG:
            result_message = self.handle_get_block(message)
        elif code == STATUS.TRANSACTION_MSG:
            result_message = self.handle_transaction(message)
        elif code == STATUS.POT:
            self.handle_sync_vote(message)
            result_message = Message(STATUS.NODE_MSG, "4")
        elif code == STATUS.UPDATE_MSG:
            result_message = self.handle_update(message)
        else:
            result_message = Message.empty_message()
        return json.dumps(result_message.__dict__)

    @staticmethod
    def check_vote_synced(vote_data):
        """
        将邻居节点发送的投票信息与本地进行对比， 投票完全一致说明投票完成
        除了需要与client的信息一致， 还需要至少在本轮和每一个client都同步过一次
        :param vote_data:
        :return:
        """
        if vote_data == {} or len(vote_data) != len(VoteCenter().vote) or not Counter().client_verify():
            return False
        for address in vote_data:
            # 当前地址的键值不存在， 说明信息没有同步
            if address not in VoteCenter().vote.keys():
                return False
            # todo: 由于是浅拷贝，会不会影响到另外一个正在写的线程
            a = VoteCenter().vote[address]
            b = vote_data[address]
            if len(a) == 0 or len(b) == 0 or len(a) != len(b):
                return False
            a = a[: -1]
            b = b[: -1]
            a.sort()
            b.sort()
            if a != b:
                return False
        return True

    def handle_handshake(self, message: dict):
        """
        状态码STATUS.HAND_SHAKE_MSG = 1， 处理握手请求
        主要进行本地和远程的区块信息更新
        :param message:
        :return:
        """
        data = message.get("data", {})
        vote_data = data.get("vote", {})
        remote_height = data.get("latest_height", 0)
        node_id = data.get("id")

        bc = BlockChain()
        block, prev_hash = bc.get_latest_block()
        local_height = -1

        # 如果当前线程没有同步过client的节点信息， 设置一次并且注册
        # upd： 保证对端节点的高度和本地一致
        if self.thread_local.client_id == -1 and remote_height == local_height:
            self.thread_local.client_id = node_id
            Counter().client_reg()

        # 获取本地高度之前检查是否存在区块
        if block:
            local_height = block.block_header.height

        # 本地高度低于远端高度， 清除交易和投票信息
        if local_height < remote_height:
            self.txs.clear()
            VoteCenter().refresh(remote_height)
            Counter().refresh()
            # Timer().refresh(remote_height)
            logging.debug("Local vote and transaction cleared.")

        # 与client通信的线程高度与数据库高度不一致， 说明新一轮共识没有同步
        if self.thread_local.height != local_height:
            self.thread_local.height = local_height
            self.thread_local.client_synced = False
            self.thread_local.server_synced = False

        # 本地高度低于邻居高度， 拉取区块
        if local_height < remote_height:
            logging.debug("Local height lower than remote height, pull block.")
            result = Message(STATUS.UPDATE_MSG, local_height)
            return result

        # 投票信息同步完成
        # todo： 逻辑修改， 在到达时间点后直接进行处理
        flg = self.check_vote_synced(vote_data)
        # 这里的逻辑实际是存在问题的， server和每个client都有建立连接， 但是只和一个client判断信息同步完成， 并且每一次都要判断
        if flg:
            a = sorted(VoteCenter().vote.items(), key=lambda x: (x[1][-1], x[0]), reverse=True)
            # 如果同步完成， 按照第一关键字为投票数，第二关键字为地址字典序来进行排序
            # x的结构： addr1: [addr2 , addr3, ..., count]
            # x[1]取后面的列表
            address = a[0][0]
            result = Message(STATUS.SYNC_MSG, address)
            return result

        if self.txs:
            # 如果服务器存在交易， 发送给client
            transaction = self.txs.pop()
            result = Message(STATUS.TRANSACTION_MSG, transaction)
            # time.sleep(2)
            return result

        try:
            genesis_block = bc[0]
        except IndexError:
            logging.error("Get genesis block error: IndexError, return empty message.")
            result = Message.empty_message()
            return result
        # 逻辑走到这里说明不需要进行其他的操作， 直接返回握手的信息
        result_data = {
            "last_height": -1,
            "genesis_block": "",
            "address": Config().get('node.address'),
            "time": time.time(),
            "id": int(Config().get('node.id')),
            "vote": VoteCenter().vote
        }

        if genesis_block:
            result_data = {
                "last_height": block.block_header.height,
                "genesis_block": genesis_block.serialize(),
                "address": Config().get('node.address'),
                "time": time.time(),
                "id": int(Config().get('node.id')),
                "vote": VoteCenter().vote
            }
        result = Message(STATUS.HAND_SHAKE_MSG, result_data)
        return result

    @staticmethod
    def handle_get_block(message: dict):
        """
        状态码STATUS.GET_BLOCK_MSG = 2， 发送邻居节点需要的block
        :param message: 需要处理的message
        :return: 返回对方需要的block数据
        """
        height = message.get("data", 1)
        bc = BlockChain()
        block = bc.get_block_by_height(height)
        result_data = block.serialize()
        result = Message(STATUS.GET_BLOCK_MSG, result_data)
        return result

    def handle_transaction(self, message: dict):
        """
        状态码为STATUS.TRANSACTION_MSG = 3
        处理客户端发送的交易信息
        将交易添加到交易内存池， 如果满了就添加到区块
        :param message: 客户端发送过来的交易信息
        :return: None
        """
        transaction_data = message.get("data", [])

        self.txs.append(transaction_data)
        transaction = Transaction.deserialize(transaction_data)
        # 如果远端的交易添加失败， 说明交易已经存在或上一轮共识结束不进行后面的操作， 避免出现重复发出共识信息
        if not self.tx_pool.add(transaction):
            return Message.empty_message()

        if self.tx_pool.is_full():
            local_address = Config().get('node.address')
            final_address = VoteCenter().local_vote()
            if final_address is None:
                final_address = local_address
            VoteCenter().vote_update(local_address, final_address, self.thread_local.height)
            result_data = {
                'vote': local_address + ' ' + final_address,
                'address': local_address,
                'time': time.time(),
                # 这里是不是每一次都要从Config中读取？或许需要优化一下
                'id': int(Config().get('node.id')),
                'height': self.thread_local.height
            }
            result = Message(STATUS.POT, result_data)
            return result
        return Message.empty_message()

    def handle_sync_vote(self, message: dict):
        """
        状态码为STATUS.POT = 4， 同步时间共识的投票信息, 将远端的投票信息加入本地
        :param message: 需要处理的message
        :return: None
        """
        data = message.get('data', {})
        vote = data.get('vote', '')
        height = data.get('height', -1)

        if height < self.thread_local.height:
            return

        address, final_address = vote.split(' ')
        # 将client发过来的投票信息添加到本地
        # 对端节点如果高度低于本地， 不接收对应的投票信息
        VoteCenter().vote_update(address, final_address, height)
        if not self.thread_local.server_synced:
            logging.debug("Add local vote information")
            address = Config().get("node.address")

            final_address = VoteCenter().local_vote()
            if final_address is not None:
                VoteCenter().vote_update(address, final_address, self.thread_local.height)
            self.thread_local.server_synced = True
        if not self.thread_local.client_synced:
            logging.debug("Synced with node {} vote info {}".format(self.thread_local.client_id, vote))
            self.thread_local.client_synced = True
            Counter().client_synced()

    def handle_update(self, message: dict):
        """
        状态码为STATUS.UPDATE_MSG = 6, 从邻居节点更新区块
        :param message: 需要处理的message
        :return: None
        """
        data = message.get("data", "")
        block = Block.deserialize(data)
        bc = BlockChain()
        try:
            # 一轮共识结束的第一个标识：收到其他节点发来的新区块
            is_added = bc.add_block_from_peers(block)

            if is_added:
                delay_params = block.transactions[0].inputs[0].delay_params
                hex_seed = delay_params.get("seed")
                seed = funcs.hex2int(hex_seed)
                Calculator().update(seed)
            # 从邻居节点更新了区块， 说明一轮共识已经结束或本地区块没有同步
            # 需要更新vote center中的信息并且设置synced为false
            self.thread_local.client_synced = False
            self.thread_local.server_synced = False
            # 从交易池中移除已有的交易
            for tx in block.transactions:
                tx_hash = tx.tx_hash
                self.tx_pool.remove(tx_hash)
        except ValueError as e:
            # todo: 失败的情况下应该进行回滚
            logging.error(e)
        return Message(STATUS.NODE_MSG, "6")
