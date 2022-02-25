import json
import logging
import socket
import time

from core.block import Block
from core.block_chain import BlockChain
from core.config import Config
from core.transaction import Transaction
from core.txmempool import TxMemPool
from node.constants import STATUS
from node.message import Message
from node.pot import ProofOfTime
from utils.dbutil import DBUtil


class Client(object):
    def __init__(self, ip, port):
        self.txs = []
        self.sock = socket.socket()

        self.sock.connect((ip, port))
        logging.info("Connect to server ip: {} port: {}".format(ip, port))
        self.vote = {}
        self.tx_pool = TxMemPool()

    def add_transaction(self, transaction):
        self.txs.append(transaction)

    def send(self, message):
        rec_message = None
        data = json.dumps(message.__dict__)
        self.sock.sendall(data.encode())

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
                        db.create('wallets', {})
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

        if rec_message is not None:
            self.handle(rec_message)

    def shake_loop(self):
        while True:
            if self.txs:
                data = self.txs[0].serialize()
                message = Message(STATUS.TRANSACTION_MSG, data)
                self.send(message)
                self.txs.clear()
            else:
                bc = BlockChain()
                latest_block, prev_hash = bc.get_latest_block()
                try:
                    genesis_block = bc[0]
                except IndexError as e:
                    genesis_block = None

                data = {
                    "last_height": -1,
                    "genesis_block": "",
                    "address": Config().get('node.address'),
                    "time": time.time(),
                    "id": Config().get('node.id'),
                    "vote": self.vote
                }

                if genesis_block:
                    data['latest_height'] = latest_block.block_header.height
                    data['genesis_block'] = genesis_block.serialize()

                send_message = Message(STATUS.HAND_SHAKE_MSG, data)
                logging.debug("Send message: {}".format(data))
                self.send(send_message)
                time.sleep(10)

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
        latest_height = data.get('latest_height', 0)
        vote_data = data['vote']

        if vote_data == {}:
            self.vote.clear()
            self.txs.clear()
        else:
            for address in vote_data:
                self.vote[address] = vote_data[address]

        bc = BlockChain()
        latest_block, prev_hash = bc.get_latest_block()

        if latest_block:
            local_height = latest_block.block_header.height
        else:
            local_height = -1

        if local_height >= latest_height:
            return
        start_height = 0 if local_height == -1 else local_height
        for i in range(start_height, latest_height + 1):
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
            # todo: 错误处理
            print(e)

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

        if self.tx_pool.is_full():
            address = Config().get('node.address')
            pot = ProofOfTime()
            final_address = pot.local_vote()

            # todo: 这一部分出现了三次， 可以考虑挪动进行代码复用
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

            message_data = {
                'vote': address + ' ' + final_address,
                'address': address,
                'time': time.time(),
                'id': int(Config().get('node.id'))
            }
            send_message = Message(STATUS.POT, message_data)
            self.send(send_message)

    def handle_pot(self, message: dict):
        data = message.get('data', {})
        vote_data = data.get('vote', '')
        address, final_address = vote_data.split(' ')
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

    def handle_sync(self, message: dict):
        data = message.get('data', '')
        address = Config().get('node.address')
        if data == address:
            transactions = self.tx_pool.package()
            bc = BlockChain()
            bc.add_new_block([transactions], self.vote)
            self.vote = {}
            self.txs = []

    def handle_update(self, message: dict):
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
