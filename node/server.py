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
from threads.calculator import Calculator
# from threads.counter import Counter
from threads.merge import MergeThread
# from threads.vote_center import VoteCenter
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
        # 连接的client的id
        self.thread_local.client_id = -1
        # client同步标志， 确认是否和所连接的client同步过一次
        self.thread_local.client_synced = False
        # server同步标志， 确认本地投票的信息是否放入到vote_center
        self.thread_local.server_synced = False
        self.thread_local.height = -1

        while True:
            if not constant.NODE_RUNNING:
                logging.debug("Receive stop signal, stop thread.")
                break

            with package_cond:
                while package_lock.locked():
                    logging.debug("Wait block package finished.")
                    package_cond.wait()

            try:
                # rec_data = conn.recv(4096 * 2)
                rec_data = TCPConnect.recv_msg(conn)
                if rec_data is None:
                    # Counter().client_close()
                    conn.close()
                    break

                rec_msg = json.loads(rec_data.decode('utf-8'))

            except ValueError:
                try:
                    # 发送信息， 如果出现错误说明连接断开
                    # conn.sendall('{"code": 0, "data": ""}'.encode())
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
                    # 发送信息， 如果出现错误说明连接断开
                    # conn.sendall(send_data.encode())
                    TCPConnect.send_msg(conn, send_data)
                except BrokenPipeError:
                    logging.info("Client lost connect, close server.")
                    server_continue = False
            if server_continue:
                # time.sleep(0.01)
                pass
            else:
                # 失去连接， 从vote center中-1
                # Counter().client_close()
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
        elif code == STATUS.POT:
            self.handle_sync_vote(message)
            result_message = Message(STATUS.NODE_MSG, "4")
        elif code == STATUS.UPDATE_MSG:
            result_message = self.handle_update(message)
        elif code == STATUS.BLOCK:
            result_message = self.handle_send_block(message)
        else:
            result_message = Message.empty_message()
        return json.dumps(result_message.__dict__)

    # @staticmethod
    # def check_vote_synced(vote_data):
    #     """
    #     将邻居节点发送的投票信息与本地进行对比， 投票完全一致说明投票完成
    #     除了需要与client的信息一致， 还需要至少在本轮和每一个client都同步过一次
    #     :param vote_data:
    #     :return:
    #     """
    #     local_vote = VoteCenter().vote
    #     if vote_data == {} or len(vote_data) != len(local_vote) or not Counter().client_verify():
    #         logging.debug("Vote data: {}".format(vote_data))
    #         logging.debug("Vote data length: {} / {}".format(len(vote_data), len(local_vote)))
    #         logging.debug("Check vote synced condition failed.")
    #         return False
    #     for address in vote_data:
    #         # 当前地址的键值不存在， 说明信息没有同步
    #         if address not in local_vote.keys():
    #             logging.debug("Address {} not in local vote key.".format(address))
    #             return False
    #         # todo: 由于是浅拷贝，会不会影响到另外一个正在写的线程
    #         a = local_vote[address]
    #         b = vote_data[address]
    #         if len(a) == 0 or len(b) == 0 or len(a) != len(b):
    #             logging.debug("Vote list length is not equal.")
    #             return False
    #         a = a[: -1]
    #         b = b[: -1]
    #         a.sort()
    #         b.sort()
    #         if a != b:
    #             logging.debug("Sorted list is not equal.")
    #             return False
    #     logging.debug("Vote list same, return True.")
    #     return True

    def handle_handshake(self, message: dict):
        """
        状态码STATUS.HAND_SHAKE_MSG = 1， 处理握手请求
        主要进行本地和远程的区块信息更新
        :param message:
        :return:
        """
        logging.debug("Server receive handshake message.")
        data = message.get("data", {})
        vote_data = data.get("vote", {})
        remote_height = data.get("latest_height", -1)
        remote_address = data.get("address")
        node_id = data.get("id")
        vote_height = data.get("vote_height", 0)

        if remote_height != -1:
            remote_block_data = data.get("latest_block", "")
            if remote_block_data != "":
                remote_block = Block.deserialize(remote_block_data)
                MergeThread().append_block(remote_block)

        bc = BlockChain()
        block, prev_hash = bc.get_latest_block()
        local_height = -1

        # 如果当前线程没有同步过client的节点信息， 设置一次并且注册
        # upd： 保证对端节点的高度和本地一致
        # if self.thread_local.client_id == -1 and remote_height == local_height:
        #     self.thread_local.client_id = node_id
        #     Counter().client_reg()

        logging.debug("Remote address {} height #{}.".format(remote_address, remote_height))

        # 获取本地高度之前检查是否存在区块
        if block:
            local_height = block.block_header.height

        # 与client通信的线程高度与数据库高度不一致， 说明新一轮共识没有同步
        if self.thread_local.height != local_height:
            logging.debug("New consensus round, refresh flags.")
            # Counter().refresh(local_height)
            self.thread_local.height = local_height
            self.thread_local.client_synced = False
            self.thread_local.server_synced = False

        # 本地高度低于邻居高度， 拉取区块
        if local_height < remote_height:
            logging.debug(
                "Local height#{} lower than remote height#{}, pull block.".format(local_height, remote_height))

            if not block:
                block, _ = bc.get_latest_block()

            try:
                block_data = block.serialize()
                logging.debug("Send local height and latest block information.")
            except AttributeError:
                block_data = ""

            data = {
                'height': local_height,
                'block': block_data
            }

            result = Message(STATUS.UPDATE_MSG, data)
            return result

        # 投票信息同步完成
        # 这里的逻辑实际是存在问题的， server和每个client都有建立连接， 但是只和一个client判断信息同步完成， 并且每一次都要判断
        # logging.debug("Server vote result send status: {}".format(self.thread_local.server_send))
        # local_votes = copy.deepcopy(VoteCenter().vote)
        # if Timer().finish() or self.check_vote_synced(vote_data):
        #     height = VoteCenter().height
        #     a = sorted(local_votes.items(), key=lambda x: (len(x[1]), x[0]), reverse=True)
        #     # 如果同步完成， 按照第一关键字为投票数，第二关键字为地址字典序来进行排序
        #     # x的结构： addr1: [addr2 , addr3, ..., count]
        #     # x[1]取后面的列表
        #     try:
        #         address = a[0][0]
        #         data = {
        #             "result": address,
        #             "height": height,
        #             "vote_info": local_votes
        #         }
        #         result = Message(STATUS.SYNC_MSG, data)
        #         logging.debug("Send vote result {}#{} to client.".format(address, VoteCenter().height))
        #         # time.sleep(0.01)
        #         return result
        #     except IndexError:
        #         # 如果本地没有投票信息直接略过
        #         logging.info("Local node has none vote information.")
        #
        # if bool(vote_data):
        #     logging.debug("Vote information is not synced, sync remote vote list.")
        #     VoteCenter().vote_sync(vote_data, vote_height)
        #     logging.debug("Vote information append to queue finished.")

        result_data = {
            "last_height": -1,
            "latest_block": "",
            "address": Config().get('node.address'),
            "time": time.time(),
            "id": int(Config().get('node.id')),
            # "vote": local_votes,
            # "vote_height": VoteCenter().height,
        }

        if not block:
            block, _ = bc.get_latest_block()

        try:
            result_data['latest_height'] = block.block_header.height
            result_data['latest_block'] = block.serialize()
        except AttributeError:
            result_data['latest_height'] = -1
            result_data['latest_block'] = ""

        if not block:
            return Message.empty_message()

        result = Message(STATUS.HAND_SHAKE_MSG, result_data)
        logging.debug("Return handshake data.")
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
        try:
            result_data = block.serialize()
            # logging.debug("Return get block message: {}".format(result_data))
        except AttributeError:
            result = Message.empty_message()
        else:
            result = Message(STATUS.GET_BLOCK_MSG, result_data)
        return result

    # def handle_sync_vote(self, message: dict):
    #     """
    #     状态码为STATUS.POT = 3， 同步时间共识的投票信息, 将远端的投票信息加入本地
    #     :param message: 需要处理的message
    #     :return: None
    #     """
    #     data = message.get('data', {})
    #     vote = data.get('vote', '')
    #     height = data.get('height', -1)
    #
    #     if height < self.thread_local.height:
    #         return
    #
    #     address, final_address = vote.split(' ')
    #     # 将client发过来的投票信息添加到本地
    #     # 对端节点如果高度低于本地， 不接收对应的投票信息
    #     VoteCenter().vote_update(address, final_address, height)
    #     if not self.thread_local.server_synced:
    #         logging.debug("Add local vote information")
    #         address = Config().get("node.address")
    #
    #         final_address = VoteCenter().local_vote(self.thread_local.height)
    #         if final_address is not None:
    #             VoteCenter().vote_update(address, final_address, self.thread_local.height)
    #         self.thread_local.server_synced = True
    #     if not self.thread_local.client_synced:
    #         logging.debug("Synced with node {} vote info {}".format(self.thread_local.client_id, vote))
    #         self.thread_local.client_synced = True
    #         Counter().client_synced(height)

    def handle_update(self, message: dict):
        """
        状态码为STATUS.UPDATE_MSG = 5, 从邻居节点更新区块
        :param message: 需要处理的message
        :return: None
        """
        data = message.get("data", "")
        block = Block.deserialize(data)
        height = block.block_header.height

        try:
            # 一轮共识结束的第一个标识：收到其他节点发来的新区块
            result = MergeThread().append_block(block)
            if result == MergeThread.STATUS_APPEND:
                # 从邻居节点更新了区块， 说明一轮共识已经结束或本地区块没有同步
                # 需要更新vote center中的信息并且设置synced为false
                self.thread_local.client_synced = False
                self.thread_local.server_synced = False
                # 从交易池中移除已有的交易
                for tx in block.transactions:
                    tx_hash = tx.tx_hash
                    self.tx_pool.remove(tx_hash)
            elif result == MergeThread.STATUS_EXISTS:
                send_msg = Message(STATUS.BLOCK, height - 1)
                return send_msg
        except ValueError as e:
            # todo: 失败的情况下应该进行回滚
            logging.error(e)
        return Message(STATUS.NODE_MSG, "6")

    @staticmethod
    def handle_send_block(message: dict):
        """
        状态码为STATUS.BLOCK = 6, 发送对应高度的区块给对端
        :param message: 包含高度信息的message
        :return:
        """
        height = message.get('data', -1)

        if height == -1:
            send_message = Message.empty_message()
            return send_message

        block = BlockChain().get_block_by_height(height)

        if block is None:
            send_message = Message.empty_message()
        else:
            send_message = Message(STATUS.GET_BLOCK_MSG, block.serialize())

        return send_message
