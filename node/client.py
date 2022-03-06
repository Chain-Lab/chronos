import json
import logging
import socket
import time

import couchdb

from core.block import Block
from core.block_chain import BlockChain
from core.config import Config
from core.transaction import Transaction
from core.txmempool import TxMemPool
from core.vote_center import VoteCenter
from node.constants import STATUS
from node.message import Message
from utils.dbutil import DBUtil


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
        发送信息给邻居节点， 在出现Broke异常的情况下说明连接端口
        :param message: 待发送信息
        """
        rec_message = None
        data = json.dumps(message.__dict__)
        try:
            self.sock.sendall(data.encode())
        except BrokenPipeError:
            logging.info("Lost connect, client close.")
            return True

        try:
            rec_data = self.sock.recv(4096 * 2)
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
        except json.decoder.JSONDecodeError as e:
            print(e)
        except BrokenPipeError:
            logging.info("Lost connect, client close.")
            return True

        if rec_message is not None:
            self.handle(rec_message)

        return False

    def shake_loop(self):
        """
        握手循环， 如果存在交易的情况下就发送交易
        :return:
        :return:
        """
        while True:
            bc = BlockChain()
            latest_block, prev_hash = bc.get_latest_block()
            if (self.tx_pool.is_full() and VoteCenter().vote == {}) or (
                    VoteCenter().has_vote and not self.send_vote):
                address = Config().get('node.address')
                final_address = VoteCenter().local_vote()
                VoteCenter().vote_update(address, final_address)
                logging.debug("Local address {} vote address {}.".format(address, final_address))

                message_data = {
                    'vote': address + ' ' + final_address,
                    'address': address,
                    'time': time.time(),
                    'id': int(Config().get('node.id'))
                }
                send_message = Message(STATUS.POT, message_data)
                self.send(send_message)
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
                    "last_height": -1,
                    "genesis_block": "",
                    "address": Config().get('node.address'),
                    "time": time.time(),
                    "id": int(Config().get('node.id')),
                    "vote": VoteCenter().vote
                }

                if genesis_block:
                    # logging.debug(genesis_block.transactions)
                    data['latest_height'] = latest_block.block_header.height
                    data['genesis_block'] = genesis_block.serialize()

                send_message = Message(STATUS.HAND_SHAKE_MSG, data)
                # logging.debug("Send message: {}".format(data))
                is_closed = self.send(send_message)
                if is_closed:
                    self.close()
                    break
                time.sleep(10)

    def handle(self, message: dict):
        code = message.get('code', 0)

        if code == STATUS.HAND_SHAKE_MSG:
            logging.debug("Send HAND_SHAKE_MSG to Server")
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
            self.txs.clear()
        else:
            VoteCenter().vote_sync(vote_data)

        bc = BlockChain()
        latest_block, prev_hash = bc.get_latest_block()

        if latest_block:
            local_height = latest_block.block_header.height
        else:
            local_height = -1

        if self.height != local_height:
            logging.debug("Synced height #{}, latest height #{}, clear information.".format(self.height, local_height))
            VoteCenter().refresh_height(local_height)
            self.send_vote = False
            self.height = latest_block.block_header.height

        if local_height >= remote_height:
            return
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

        try:
            bc.add_block_from_peers(block)
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
        data = message.get('data', {})
        transaction = Transaction.deserialize(data)
        self.tx_pool.add(transaction)

        bc = BlockChain()
        latest_block, _ = bc.get_latest_block()

        if self.tx_pool.is_full():
            address = Config().get('node.address')
            final_address = VoteCenter().local_vote()

            VoteCenter().vote_update(address, final_address)

            message_data = {
                'vote': address + ' ' + final_address,
                'address': address,
                'time': time.time(),
                'id': int(Config().get('node.id'))
            }
            send_message = Message(STATUS.POT, message_data)
            self.send(send_message)

    @staticmethod
    def handle_pot(message: dict):
        """
        状态码为STATUS.POT = 4, 进行时间共识投票
        """
        data = message.get('data', {})
        vote_data = data.get('vote', '')
        address, final_address = vote_data.split(' ')
        VoteCenter().vote_update(address, final_address)

    def handle_sync(self, message: dict):
        """
        状态码为STATUS.SYNC_MSG = 5, 该节点为共识节点， 生成新区块
        :param message: 待处理的message
        :return: None
        """
        data = message.get('data', '')
        address = Config().get('node.address')
        if data == address:
            transactions = self.tx_pool.package()

            # 如果取出的交易数据是None， 说明另外一个线程已经打包了， 就不用再管
            if transactions is None:
                return

            bc = BlockChain()
            bc.add_new_block([transactions], VoteCenter().vote)
            logging.debug("Package new block.")
            self.txs = []

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
