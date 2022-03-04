import json
import logging
import socket
import threading
import time

from core.block import Block
from core.block_chain import BlockChain
from core.config import Config
from core.pot import ProofOfTime
from core.transaction import Transaction
from core.txmempool import TxMemPool
from core.vote_center import VoteCenter
from node.constants import STATUS
from node.message import Message


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
        self.vote = {}
        self.txs = []
        self.tx_pool = TxMemPool()

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
        类的运行函数， 开一个线程进行监听
        :return: None
        """
        thread = threading.Thread(target=self.listen_loop, args=())
        thread.start()

    def handle_loop(self, conn, address):
        """
        处理client信息的循环， 接收消息并返回信息
        :param conn: 与client的socket连接
        :param address:
        :return: None
        """
        rec_msg = None
        continue_server = True
        while True:
            try:
                rec_data = conn.recv(4096 * 2)
                rec_msg = json.loads(rec_data.decode('utf-8'))

            except ValueError as e:
                try:
                    # 发送信息， 如果出现错误说明连接断开
                    conn.sendall('{"code": 0, "data": ""}'.encode())
                except BrokenPipeError:
                    logging.info("Client lost connect, close server.")
                    continue_server = False

            if rec_msg is not None:
                send_data = self.handle(rec_msg)
                try:
                    # 发送信息， 如果出现错误说明连接断开
                    conn.sendall(send_data.encode())
                except BrokenPipeError:
                    logging.info("Client lost connect, close server.")
                    continue_server = False
            if continue_server:
                time.sleep(5)
            else:
                break

    def handle(self, message: dict):
        """
        :param message: 从client接收到的待处理的message
        :return: 消息处理完成后应该返回的数据
        """
        code = message.get('code', 0)
        if code == STATUS.HAND_SHAKE_MSG:
            logging.debug("Receive message code: HANDSHAKE")
            result_message = self.handle_handshake(message)
        elif code == STATUS.GET_BLOCK_MSG:
            logging.debug("Receive message code: GET_BLOCK")
            result_message = self.handle_get_block(message)
        elif code == STATUS.TRANSACTION_MSG:
            logging.debug("Receive message code: TRANSACTION")
            result_message = self.handle_transaction(message)
        elif code == STATUS.POT:
            logging.debug("Receive message code: POT")
            self.handle_sync_vote(message)
            result_message = Message(STATUS.NODE_MSG, "4")
        elif code == STATUS.UPDATE_MSG:
            logging.debug("Receive message code: UPDATE")
            result_message = self.handle_update(message)
        else:
            result_message = Message.empty_message()
        return json.dumps(result_message.__dict__)

    def check_vote_synced(self, vote_data):
        """
        将邻居节点发送的投票信息与本地进行对比， 投票完全一致说明投票完成
        :param vote_data:
        :return:
        """
        if vote_data == {} or len(vote_data) != len(self.vote):
            return False
        logging.debug("Receive vote_data: {}".format(vote_data))
        for address in vote_data:
            if address not in self.vote.keys():
                return False
            a = self.vote[address]
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
        data = message.get("data", "")
        vote_data = data.get("vote", {})
        remote_height = data.get("latest_height", 0)

        bc = BlockChain()
        block, prev_hash = bc.get_latest_block()
        local_height = -1

        # 获取本地高度之前检查是否存在区块
        if block:
            local_height = block.block_header.height

        # 本地高度不等于远端高度， 清除交易和投票信息
        if local_height != remote_height:
            self.txs.clear()
            self.vote.clear()

        # 本地高度低于邻居高度， 拉取区块
        if local_height < remote_height:
            result = Message(STATUS.UPDATE_MSG, local_height)
            return result

        # 投票信息同步完成
        flg = self.check_vote_synced(vote_data)

        if flg:
            a = sorted(self.vote.items(), key=lambda x: x[-1], reverse=False)
            address = a[0][0]
            result = Message(STATUS.SYNC_MSG, address)
            return result

        if self.txs:
            # 如果服务器存在交易， 发送给client
            result = Message(STATUS.TRANSACTION_MSG, self.txs[0])
            time.sleep(2)
            self.txs = self.txs[1:]
            return result

        try:
            genesis_block = bc[0]
        except IndexError as e:
            genesis_block = None
            logging.error("Get genesis block error: IndexError, return empty message.")
            result = Message.empty_message()
            return result

        result_data = {
            "last_height": -1,
            "genesis_block": "",
            "address": Config().get('node.address'),
            "time": time.time(),
            "id": int(Config().get('node.id')),
            "vote": self.vote
        }

        if genesis_block:
            result_data = {
                "last_height": block.block_header.height,
                "genesis_block": genesis_block.serialize(),
                "address": Config().get('node.address'),
                "time": time.time(),
                "id": int(Config().get('node.id')),
                "vote": self.vote
            }
        result = Message(STATUS.HAND_SHAKE_MSG, result_data)
        return result

    @staticmethod
    def handle_get_block(message: dict):
        """
        状态码STATUS.GET_BLOCK_MSG = 2， 邻居节点或许所需的区块
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
        self.tx_pool.add(transaction)

        if self.tx_pool.is_full():
            local_address = Config().get('node.address')
            final_address = ProofOfTime().local_vote()

            logging.debug("Local address {}, final vote address is: {}".format(local_address, final_address))
            if final_address not in self.vote:
                self.vote[final_address] = [local_address, 1]
            else:
                lst = self.vote[final_address]
                if local_address not in lst:
                    lst.insert(0, local_address)
                    logging.debug("lst[-1] = {}".format(lst[-1]))
                    logging.debug("lst = {}".format(lst))
                    # todo: 是否能够直接+1， 而不用中间变量
                    #  需查看list的结构再进行处理
                    num = lst[-1]
                    num += 1
                    lst[-1] = num
                    logging.debug("lst = {}".format(lst))
                    logging.debug("lst[-1] = {}".format(lst[-1]))
                    self.vote[final_address] = lst
            result_data = {
                'vote': local_address + ' ' + final_address,
                'address': local_address,
                'time': time.time(),
                'id': int(Config().get('node.id'))
            }
            result = Message(STATUS.POT, result_data)
            return result

    def handle_sync_vote(self, message: dict):
        """
        状态码为STATUS.POT = 4， 同步时间共识的投票信息, 将远端的投票信息加入本地
        :param message: 需要处理的message
        :return: None
        """
        data = message.get('data', {})
        vote = data.get('vote', '')
        address, final_address = vote.split(' ')
        if final_address not in self.vote:
            self.vote[final_address] = [address, 1]
        else:
            lst = self.vote[final_address]
            if address not in lst:
                lst.insert(0, address)
                num = lst[-1]
                num += 1
                lst[-1] = num
                self.vote[final_address] = lst

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
            bc.add_block_from_peers(block)
            logging.debug("Receive block, refresh vote center.")
            VoteCenter().refresh_height(block.block_header.height)
            for tx in block.transactions:
                tx_hash = tx.tx_hash
                self.tx_pool.remove(tx_hash)
        except ValueError as e:
            logging.error(e)
        return Message(STATUS.NODE_MSG, "6")
