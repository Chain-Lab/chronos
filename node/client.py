import json
import logging
import socket
import threading
import time

import couchdb

from core.block import Block
from core.block_chain import BlockChain
from core.config import Config
from core.transaction import Transaction
from core.txmempool import TxMemPool
from node.counter import Counter
from node.vote_center import VoteCenter
from node.constants import STATUS
from node.message import Message
from node.timer import Timer
from utils.network import TCPConnect
from utils.dbutil import DBUtil
from utils import funcs
from node.calculator import Calculator


class Client(object):
    def __init__(self, ip, port):
        self.txs = []
        self.sock = socket.socket()

        self.sock.connect((ip, port))
        logging.info("Connect to server ip: {} port: {}".format(ip, port))
        self.tx_pool = TxMemPool()
        self.send_vote = False
        self.height = -1

    def add_transaction(self, transaction):
        """
        添加交易到本地client, 即直接append到txs列表中
        :param transaction: 待添加的交易
        :return: None
        """
        self.txs.append(transaction)

    def send(self, message):
        """
        发送信息给邻居节点， 在出现Broke异常的情况下说明连接断开
        :param message: 待发送信息
        """
        rec_message = None
        data = json.dumps(message.__dict__)
        try:
            # self.sock.sendall(data.encode())
            TCPConnect.send_msg(self.sock, data)
        except BrokenPipeError:
            logging.info("Lost connect, client close.")
            return True

        try:
            # rec_data = self.sock.recv(4096 * 2)
            rec_data = TCPConnect.recv_msg(self.sock)
            if rec_data == b"":
                return True
            rec_message = json.loads(rec_data.decode('utf-8'))

            data = rec_message.get('data', '')

            if isinstance(data, dict):
                address = data.get('address', '')
                if address != "":
                    db = DBUtil(Config().get('database.url'))
                    old_wallets = db.get('wallets')

                    if old_wallets is None:
                        logging.info('Remote node wallet is not created in database, create new record.')
                        try:
                            db.create('wallets', {})
                        except couchdb.ResourceConflict:
                            logging.error("Database wallet: resource conflict")
                        old_wallets = db.get('wallets')
                    old_wallets.update({
                        address: {
                            'time': data.get('time', ''),
                            'id': int(Config().get('node.id'))
                        }
                    })
                    db.update([old_wallets])
        # 在信息错误或连接断开时会产生该错误
        except json.decoder.JSONDecodeError as e:
            logging.debug(data)
            logging.error(e)
        except ConnectionResetError:
            return True

        if rec_message is not None:
            self.handle(rec_message)

        return False

    def shake_loop(self):
        """
        握手循环， 如果存在交易的情况下就发送交易
        :return:
        """
        thread_obj = threading.current_thread()
        thread_obj.name = "Client Thread - " + thread_obj.getName().split("-")[-1]
        while True:
            bc = BlockChain()
            latest_block, prev_hash = bc.get_latest_block()
            # client开始一轮共识的逻辑：没有待发送交易，交易池为空且没有本地投票数据
            # 或已经投票但是client没有发送
            # 或到达时间并且没有发送投票信息
            if (not self.txs and self.tx_pool.is_full() and VoteCenter().vote == {}) or (
                    not self.txs and VoteCenter().has_vote and not self.send_vote) or (
                    not self.txs and Timer().reach() and not self.send_vote):
                address = Config().get('node.address')
                final_address = VoteCenter().local_vote()
                if final_address is None:
                    final_address = address
                VoteCenter().vote_update(address, final_address, self.height)

                message_data = {
                    'vote': address + ' ' + final_address,
                    'address': address,
                    'time': time.time(),
                    'id': int(Config().get('node.id')),
                    'height': self.height
                }
                send_message = Message(STATUS.POT, message_data)
                self.send(send_message)
                # 不论是否进行过数据的发送，都设置为True
                self.send_vote = True

            if self.txs:
                # 如果本地存在交易， 将交易发送到邻居节点
                # todo： 如果有多个交易的情况下需要进行处理， 目前仅仅针对一个交易
                #  修改clear的逻辑
                logging.debug("Send transaction to peer.")
                data = self.txs[0].serialize()
                self.tx_pool.add(self.txs[0])
                message = Message(STATUS.TRANSACTION_MSG, data)
                is_closed = self.send(message)
                if is_closed:
                    self.close()
                    break
                self.txs.clear()
            else:
                try:
                    genesis_block = bc[0]
                except IndexError as e:
                    genesis_block = None

                data = {
                    "latest_height": -1,
                    "genesis_block": "",
                    "address": Config().get('node.address'),
                    "time": time.time(),
                    "id": int(Config().get('node.id')),
                    "vote": VoteCenter().vote
                }

                if genesis_block:
                    # logging.debug(genesis_block.transactions)
                    # 如果存在创世区块， 发送创世区块
                    # 考虑一下创世区块的用处
                    data['latest_height'] = latest_block.block_header.height
                    data['genesis_block'] = genesis_block.serialize()

                send_message = Message(STATUS.HAND_SHAKE_MSG, data)
                # logging.debug("Send message: {}".format(data))
                is_closed = self.send(send_message)
                if is_closed:
                    self.close()
                    break
                time.sleep(1)

    def handle(self, message: dict):
        code = message.get('code', 0)

        if code == STATUS.HAND_SHAKE_MSG:
            self.handle_shake(message)
        elif code == STATUS.GET_BLOCK_MSG:
            self.handle_get_block(message)
        elif code == STATUS.TRANSACTION_MSG:
            self.handle_transaction(message)
        elif code == STATUS.POT:
            self.handle_pot(message)
        elif code == STATUS.SYNC_MSG:
            self.handle_sync(message)
        elif code == STATUS.UPDATE_MSG:
            self.handle_update(message)

    def handle_shake(self, message: dict):
        """
        状态码为STATUS.HAND_SHAKE_MSG = 1, 进行握手处理
        :param message: 待处理的消息
        :return: None
        """
        data = message.get('data', {})
        remote_height = data.get('latest_height', 0)
        vote_data = data['vote']

        if vote_data == {}:
            # self.txs.clear()
            pass
        else:
            VoteCenter().vote_sync(vote_data, remote_height)

        bc = BlockChain()
        latest_block, prev_hash = bc.get_latest_block()

        if latest_block:
            local_height = latest_block.block_header.height
        else:
            local_height = -1

        if self.height != local_height:
            # 当前线程最后共识的高度低于最新高度， 更新共识信息
            VoteCenter().refresh(local_height)
            self.send_vote = False
            self.height = local_height

        if local_height >= remote_height:
            return

        # 发送邻居节点没有的区块
        start_height = 0 if local_height == -1 else local_height
        for i in range(start_height, remote_height + 1):
            send_msg = Message(STATUS.GET_BLOCK_MSG, i)
            self.send(send_msg)

    @staticmethod
    def handle_get_block(message: dict):
        """
        状态码为STATUS.GET_BLOCK_MSG = 2, 处理服务器发送过来的区块数据
        :param message: 包含区块数据的消息
        :return: None
        """
        # todo: 这一句挪到前面统一处理？
        data = message.get('data', {})
        block = Block.deserialize(data)
        bc = BlockChain()
        height = block.block_header.height

        try:
            is_added = bc.add_block_from_peers(block)
            if is_added:
                Counter().refresh()
                Timer().refresh(height)
                delay_params = block.transactions[0].inputs[0].delay_params
                hex_seed = delay_params.get("seed")
                hex_pi = delay_params.get("pi")
                seed = funcs.hex2int(hex_seed)
                pi = funcs.hex2int(hex_pi)
                Calculator().update(seed, pi)
        except ValueError as e:
            # todo: 这里应该需要进行回滚， 但是回滚涉及到线程安全问题， 需要重新考虑
            logging.error(e)

    def handle_transaction(self, message: dict):
        """
        状态码为STATUS.TRANSACTION_MSG = 3
        处理服务器发送过来的交易， 将交易添加到交易池
        :param message: 包含交易数据的消息
        :return: None
        """
        # 可能出现的问题： 在client更新本地高度之后， 收到服务器发送过来的交易，而此时交易池还没有清空，又以更新完成的高度去进行一次投票
        # upd： server端接收到其他节点发送的区块后，会从交易池中移除交易，与此同时tx_pool是无法再次添加同一笔交易的, 也无法触发下面的逻辑
        data = message.get('data', {})
        transaction = Transaction.deserialize(data)
        if not self.tx_pool.add(transaction):
            return

        bc = BlockChain()
        latest_block, _ = bc.get_latest_block()

        if self.tx_pool.is_full():
            address = Config().get('node.address')
            final_address = VoteCenter().local_vote()

            # 如果本地投票信息为空， 说明该节点不是共识节点或者连接的其他节点不是共识节点
            if final_address is None:
                final_address = address

            VoteCenter().vote_update(address, final_address, self.height)

            message_data = {
                'vote': address + ' ' + final_address,
                'address': address,
                'time': time.time(),
                'id': int(Config().get('node.id')),
                'height': self.height
            }
            send_message = Message(STATUS.POT, message_data)
            self.send(send_message)

    def handle_pot(self, message: dict):
        """
        状态码为STATUS.POT = 4, 进行时间共识投票
        """
        data = message.get('data', {})
        vote_data = data.get('vote', '')
        height = data.get('height', -1)

        if height < self.height:
            return

        address, final_address = vote_data.split(' ')
        VoteCenter().vote_update(address, final_address, height)

    def handle_sync(self, message: dict):
        """
        状态码为STATUS.SYNC_MSG = 5, 该节点为共识节点， 生成新区块
        :param message: 待处理的message
        :return: None
        """
        # 一轮共识结束的第二个标志：本地被投票为打包区块的节点，产生新区块
        data = message.get('data', '')
        address = Config().get('node.address')
        logging.debug("Receive package wallet is: {}".format(data))
        if data == address:
            transactions = self.tx_pool.package(self.height + 1)

            # 如果取出的交易数据是None， 说明另外一个线程已经打包了， 就不用再管
            # upd: 在新的逻辑里面，不论节点交易池是否存在交易都会进行区块的打包
            if transactions is None:
                return

            bc = BlockChain()
            bc.add_new_block(transactions, VoteCenter().vote, Calculator().delay_params)
            # todo: 这里假设能够正常运行, 需要考虑一下容错
            block, _ = bc.get_latest_block()
            height = block.block_header.height
            Timer().refresh(height)
            Calculator().update()
            logging.debug("Package new block.")
            self.txs.clear()

    def handle_update(self, message: dict):
        """
        状态码为STATUS.UPDATE_MSG = 6, 拉取最新的区块发送给server
        :param message: 待处理的message
        :return: None
        """
        height = message.get('data', '')
        address = Config().get('node.address')
        bc = BlockChain()
        latest_block, prev_hash = bc.get_latest_block()

        if latest_block is None:
            return

        local_height = latest_block.block_header.height
        for i in range(height + 1, local_height + 1):
            block = bc.get_block_by_height(i)
            data = block.serialize()
            data['address'] = address
            data['time'] = time.time()
            data['id'] = int(Config().get('node.id'))
            send_message = Message(STATUS.UPDATE_MSG, data)
            self.send(send_message)

    def close(self):
        self.sock.close()
