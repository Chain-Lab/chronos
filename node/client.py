import copy
import json
import logging
import socket
import threading
import time

import couchdb

from core.block import Block
from core.block_chain import BlockChain
from core.config import Config
from core.txmempool import TxMemPool
from node.constants import STATUS
from node.message import Message
from node.timer import Timer
from threads.calculator import Calculator
from threads.merge import MergeThread
from threads.vote_center import VoteCenter
from utils.dbutil import DBUtil
from utils.locks import package_lock, package_cond
from utils.network import TCPConnect

from utils import constant

class Client(object):
    # Client线程类， 多个client之间相互独立， 不共享变量
    def __init__(self, ip, port):
        self.txs = []
        self.sock = socket.socket()

        self.sock.connect((ip, port))
        logging.info("Connect to server ip: {} port: {}".format(ip, port))

        # 交易池， 单例
        self.tx_pool = TxMemPool()

        # 自身线程是否发送过投票信息
        self.send_vote = False

        # 目前client的处理高度
        self.height = -1

        # 最新区块的数据
        self.new_block = None

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

        # 是否打包了区块
        packaged = False
        while True:
            if not constant.NODE_RUNNING:
                logging.debug("Receive stop signal, stop thread.")
                break

            # 在本地进行打包区块时让出cpu资源
            with package_cond:
                while package_lock.locked():
                    logging.debug("Wait block package finished.")
                    package_cond.wait()
                    packaged = True

            # get_latest_block会返回None导致线程挂掉， 需要catch一下
            try:
                latest_block, prev_hash = bc.get_latest_block()
            except TypeError:
                continue

            # 如果打包了区块， 发送新的区块给对端
            if packaged:
                try:
                    # 本次对话的一个出口， 发送当前的区块
                    send_message = Message(STATUS.UPDATE_MSG, self.new_block.serialize())
                    self.send(send_message)
                except AttributeError:
                    pass
                packaged = False

            # 获取本地最新区块的高度
            try:
                height = latest_block.block_header.height
            except AttributeError:
                height = -1

            if self.height < height:
                # 当前线程最后共识的高度低于最新高度， 更新共识信息
                self.send_vote = False
                self.height = height
                logging.debug("Refresh client instance height information.")

            # v1.1.2 upd: 删除发送交易逻辑， 改为gossip协议使用UDP进行交易的广播
            logging.debug("Consensus data send status: {}".format(self.send_vote))
            logging.debug("Vote center vote status: {}".format(VoteCenter().has_vote))

            # 开始时间共识投票的开始： 交易池满并且投票信息为空 或 本地已经投票但是没有发送投票信息 或 到达投票时间点并且没有发送投票信息
            if (self.tx_pool.is_full() and not bool(VoteCenter().vote)) or (
                    VoteCenter().has_vote and not self.send_vote) or (
                    Timer().reach() and not self.send_vote):
                logging.debug("Start consensus.")
                address = Config().get('node.address')
                # 本地进行一次投票， 如果已经投票过了会直接返回地址
                final_address = VoteCenter().local_vote(height)
                if final_address is None:
                    final_address = address

                if final_address != -1:
                    VoteCenter().vote_update(address, final_address, self.height)
                    logging.debug("Send local vote information to server.")

                    message_data = {
                        'vote': address + ' ' + final_address,
                        'address': address,
                        'time': time.time(),
                        'id': int(Config().get('node.id')),
                        'height': self.height
                    }
                    # 发送投票信息给对端的server进行处理
                    send_message = Message(STATUS.POT, message_data)
                    logging.debug("Send consensus address to server.")
                    self.send(send_message)
                    # 不论是否进行过数据的发送，都设置为True
                    self.send_vote = True

            logging.debug("Send vote list to server.")
            data = {
                "latest_height": -1,
                "latest_block": "",
                "address": Config().get('node.address'),
                "time": time.time(),
                "id": int(Config().get('node.id')),
                "vote": VoteCenter().vote,
                "vote_height": VoteCenter().height
            }

            if not latest_block:
                latest_block, _ = bc.get_latest_block()

            try:
                data['latest_height'] = latest_block.block_header.height
                data['latest_block'] = latest_block.serialize()
            except AttributeError:
                data['latest_height'] = -1
                data['latest_block'] = ""

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
        elif code == STATUS.POT:
            self.handle_pot(message)
        elif code == STATUS.SYNC_MSG:
            self.handle_sync(message)
        elif code == STATUS.UPDATE_MSG:
            self.handle_update(message)
        elif code == STATUS.BLOCK:
            self.handle_send_block(message)

    def handle_shake(self, message: dict):
        """
        状态码为STATUS.HAND_SHAKE_MSG = 1, 进行握手处理
        :param message: 待处理的消息
        :return: None
        """
        logging.debug("Receive handshake status code.")
        data = message.get('data', {})
        remote_height = data.get('latest_height', -1)
        vote_height = data.get('vote_height', 0)
        vote_data = data['vote']
        remote_address = data.get("address")

        logging.debug("Remote address {} height #{}.".format(remote_address, remote_height))

        # 如果对端的高度不是-1， 将区块放入到Merge线程进行处理
        if remote_height != -1:
            remote_block_data = data.get("latest_block", "")
            if remote_block_data != "":
                remote_block = Block.deserialize(remote_block_data)
                MergeThread().append_block(remote_block)

        if bool(vote_data):
            VoteCenter().vote_sync(vote_data, vote_height)

        bc = BlockChain()
        latest_block, prev_hash = bc.get_latest_block()

        if latest_block:
            local_height = latest_block.block_header.height
        else:
            local_height = -1

        if local_height >= remote_height:
            logging.debug("Local height >= remote height.")
            return

        # 请求本地没有的区块
        start_height = 0 if local_height == -1 else local_height
        for i in range(start_height, remote_height + 1):
            logging.debug("Client pull block#{}.".format(i))
            send_msg = Message(STATUS.GET_BLOCK_MSG, i)
            self.send(send_msg)

    def handle_get_block(self, message: dict):
        """
        状态码为STATUS.GET_BLOCK_MSG = 2, 处理服务器发送过来的区块数据
        :param message: 包含区块数据的消息
        :return: None
        """
        data = message.get('data', {})
        block = Block.deserialize(data)
        height = block.block_header.height

        logging.debug("Receive server block data: {}".format(data))
        result = MergeThread().append_block(block)
        if result == MergeThread.STATUS_EXISTS:
            send_msg = Message(STATUS.BLOCK, height - 1)
            self.send(send_msg)

    def handle_pot(self, message: dict):
        """
        状态码为STATUS.POT = 3, 进行时间共识投票
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
        状态码为STATUS.SYNC_MSG = 4, 该节点为共识节点， 生成新区块
        :param message: 待处理的message
        :return: None
        """
        # 一轮共识结束的第二个标志：本地被投票为打包区块的节点，产生新区块
        data = message.get('data', {})
        address = Config().get('node.address')
        dst_address = data.get("result", "0")
        vote_height = data.get("height", 0)
        logging.debug("Client receive package address: {} height {}".format(address, vote_height))

        latest_block, _ = BlockChain().get_latest_block()

        if latest_block.height != vote_height:
            logging.info("Vote height is not equal local height.")
            return

        vote_data = data.get("vote_info", {})

        if bool(vote_data):
            VoteCenter().vote_sync(vote_data, vote_height)

        if address == dst_address:
            if package_lock.locked():
                logging.debug("Package locked.")
                return
            package_lock.acquire()
            vote_data = copy.deepcopy(VoteCenter().vote)

            # 用于验证本地是否打包节点的逻辑
            a = sorted(vote_data.items(), key=lambda x: (x[1][-1], x[0]), reverse=True)
            try:
                if a[0][0] != address:
                    package_lock.release()
                    with package_cond:
                        package_cond.notify_all()
                    logging.debug("Local address is not package node.")
                    logging.debug("Local vote list#{}: {}".format(VoteCenter().height, a))
                    return
            except IndexError:
                package_lock.release()
                with package_cond:
                    package_cond.notify_all()
                logging.debug("Local address is not package node.")
                logging.debug("Local vote list#{}: {}".format(VoteCenter().height, a))
                return

            start_time = time.time()

            logging.debug("Lock package lock. Start package memory pool.")
            transactions = self.tx_pool.package(vote_height + 1)
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
            logging.debug("Start package new block.")
            self.new_block = bc.package_new_block(transactions, vote_data, Calculator().delay_params)

            end_time = time.time()
            logging.debug("Package block use {}s include count {}".format(end_time - start_time, len(transactions)))

            # 如果区块打包失败， 则将交易池回退到上一个高度
            if not self.new_block:
                self.tx_pool.set_height(vote_height)
            package_lock.release()

            with package_cond:
                logging.debug("Notify all thread.")
                package_cond.notify_all()

            if self.new_block:
                logging.debug("Append new block to merge thread.")
                MergeThread().append_block(self.new_block)
            logging.debug("Package new block.")

    def handle_update(self, message: dict):
        """
        状态码为STATUS.UPDATE_MSG = 5, 拉取最新的区块发送给server
        :param message: 待处理的message
        :return: None
        """
        data = message.get('data', {})

        if not data:
            return

        height = data.get('height')
        block_data = data.get('block')
        address = Config().get('node.address')
        bc = BlockChain()
        latest_block, prev_hash = bc.get_latest_block()

        if latest_block is None:
            return

        if block_data != "":
            block = Block.deserialize(block_data)
            logging.debug("Append peer block#{}.".format(block.block_header.hash))
            MergeThread().append_block(block)

        local_height = latest_block.block_header.height
        start_height = height + 1
        for i in range(start_height, local_height + 1):
            logging.debug("Client send block #{}.".format(i))
            block = bc.get_block_by_height(i)
            data = block.serialize()
            data['address'] = address
            data['time'] = time.time()
            data['id'] = int(Config().get('node.id'))
            send_message = Message(STATUS.UPDATE_MSG, data)
            self.send(send_message)

    def handle_send_block(self, message: dict):
        """
        状态码为STATUS.BLOCK = 6, 发送对应高度的区块给对端
        这里逻辑和状态码为2的逻辑是一样的， 但是为了保证C/S的统一所以还是需要定义一下
        :param message: 包含高度信息的message
        :return:
        """
        height = message.get('data', -1)

        if height == -1:
            send_message = Message.empty_message()
            self.send(send_message)
            return
        block = BlockChain().get_block_by_height(height)

        if block is None:
            send_message = Message.empty_message()
        else:
            send_message = Message(STATUS.UPDATE_MSG, block.serialize())

        self.send(send_message)

    def close(self):
        self.sock.close()
