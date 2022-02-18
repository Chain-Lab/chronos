import json
import socket
import threading
import time

from core.txmempool import TxMemPool
from core.block import Block
from core.blockchain import BlockChain
from core.transaction import Transaction
from core.config import Config
from node.message import Message
from node.constants import STATUS
from node.pot import ProofOfTime


class TCPServer(object):
    def __init__(self, ip, port):
        """
        由cli调用时传入ip和端口来进行初始化， 尽量保证模块独立
        :param ip: ip地址，一般为localhost
        :param port: 端口
        """
        self.sock = socket.socket()
        self.ip = ip
        self.port = port
        self.vote = {}
        self.txs = []
        self.tx_pool = TxMemPool()

    def listen(self):
        self.sock.bind((self.ip, self.port))
        self.sock.listen(10)

    def run(self):
        pass

    def handle_loop(self, conn, address):
        rec_msg = None
        while True:
            try:
                rec_data = conn.recv(4096 * 2)
                rec_msg = json.loads(rec_data.decode('utf-8'))

            except ValueError as e:
                conn.sendall('{"code": 0, "data": ""}'.encode())

            if rec_msg is not None:
                send_data = self.handle(rec_msg)
                conn.sendall(send_data.encode())

            time.sleep(5)

    def handle(self, message: dict):
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
            result_message = Message(STATUS.NODE_MSG, "6")
        else:
            result_message = Message.empty_message()
        return json.dumps(result_message.__dict__)

    def listen_loop(self):
        while True:
            conn, address = self.sock.accept()
            thread = threading.Thread(target=self.handle_loop, args=(conn, address))
            thread.start()

    def check_vote_synced(self, vote_data):
        """
        将邻居节点发送的投票信息与本地进行对比， 投票完全一致说明投票完成
        :param vote_data:
        :return:
        """
        if vote_data == {} or len(vote_data) != len(self.vote):
            return False
        for address in vote_data:
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
        # todo: 用于共识的投票信息， 后续在设计完成相关的共识RPC接口后再接入
        vote_data = data.get("vote", {})
        height = data.get("latest_height", 0)

        bc = BlockChain()
        block, prev_hash = bc.get_latest_block()
        local_height = -1

        if block:
            local_height = block.block_header.height

        if local_height != height:
            self.txs.clear()
            self.vote.clear()

        if local_height < height:
            result = Message(STATUS.UPDATE_MSG, local_height)
            return result

        flg = self.check_vote_synced(vote_data)

        if flg:
            a = sorted(self.vote.items(), key=lambda x: x[-1], reverse=False)
            address = a[0][0]
            result = Message(STATUS.SYNC_MSG, address)
            return result

        if self.txs:
            result = Message(STATUS.TRANSACTION_MSG, self.txs[0])
            time.sleep(2)
            self.txs = self.txs[1:]
            return result

        try:
            genesis_block = bc[0]
        except IndexError as e:
            genesis_block = None

        result_data = {
            "last_height": -1,
            "genesis_block": "",
            # todo: 用于进行共识的信息， 后续根据对应接口进行操作
            "address": Config().get('node.address'),
            "time": time.time(),
            # "id": w.id,
            "vote": self.vote
        }

        if genesis_block:
            result_data = {
                "last_height": block.block_header.height,
                "genesis_block": genesis_block.serialize(),
                "address": Config().get('node.address'),
                "time": time.time(),
                # "id": w.id,
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

            if final_address not in self.vote:
                self.vote[final_address] = [local_address, 1]
            else:
                lst = self.vote[final_address]
                if local_address not in lst:
                    lst.insert(0, local_address)
                    # todo: 是否能够直接+1， 而不用中间变量
                    #  需查看list的结构再进行处理
                    num = lst[-1]
                    num += 1
                    lst[-1] = num
                    self.vote[final_address] = lst
            result_data = {
                'vote': local_address + ' ' + final_address,
                'address': local_address,
                # todo: 数据信息待确定
                'time': time.time(),
                # 'id': w.id
            }
            result = Message(STATUS.POT, result_data)
            return result

    def handle_sync_vote(self, message: dict):
        """
        状态码为STATUS.POT = 4， 同步时间共识的投票信息
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

    @staticmethod
    def update_msg(message: dict):
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
        except ValueError as e:
            # todo: 日志记录
            print(e)

