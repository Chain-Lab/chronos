# import copy
# import json
# import logging
# import socket
# import threading
# import time
#
# from core.block_chain import BlockChain
# from node.constants import STATUS
# from core.config import Config
# from core.txmempool import TxMemPool
# from utils.network import TCPConnect
# from utils.leveldb import LevelDB
#
# class Client(object):
#     def __init__(self, ip, port):
#         self.sock = socket.socket()
#
#         self.sock.connect((ip, port))
#         logging.info("Connect to server ip: {}, port: {}".format(ip, port))
#
#         # 交易池
#         self.tx_pool = TxMemPool()
#
#     def send(self, message):
#         """
#         发送信息给邻居节点， 在出现 Broke 异常时说明连接端口
#
#         Args:
#             message: 需要发送的消息
#         """
#         recv_message = None
#         data = json.dumps(message.__dict__)
#
#         try:
#             TCPConnect.send_msg(self.sock, data)
#         except BrokenPipeError:
#             logging.error("Lost connect, client close.")
#             return True
#
#         try:
#             # 接收server的数据
#             # rec_data = self.sock.recv(4096 * 2)
#             recv_data = TCPConnect.recv_msg(self.sock)
#             if recv_data is None:
#                 logging.debug("Receive data is empty")
#                 return True
#             rec_message = json.loads(recv_data.decode('utf-8'))
#
#             data = rec_message.get('data', '')
#
#             if isinstance(data, dict):
#                 address = data.get('address', '')
#                 if address != "":
#                     db = LevelDB()
#                     old_wallets = db.get('wallets')
#
#                     if old_wallets is None:
#                         logging.info('Remote node wallet is not created in database, create new record.')
#                         db.insert('wallets', {})
#                         old_wallets = db.get('wallets')
#                     old_wallets.update({
#                         address: {
#                             'time': data.get('time', ''),
#                             'id': int(Config().get('node.id'))
#                         }
#                     })
#                     db.insert("wallets", old_wallets)
#         # 在信息错误或连接断开时会产生该错误
#         except json.decoder.JSONDecodeError as e:
#             logging.debug(data)
#             logging.error(e)
#         except ConnectionResetError:
#             return True
#
#         if recv_message is not None:
#             try:
#                 self.handle(recv_message)
#             # 在出现异常的情况下不断开连接， 保证线程能够正常运行， 对于具体异常的处理待完成
#             except:
#                 return False
#
#         return False
#
#     def shake_loop(self):
#         """
#         通信循环体
#         """
#         thread_obj = threading.current_thread()
#         thread_obj.name = "Client Thread - " + thread_obj.name.split("-")[-1]
#
#         bc = BlockChain()
#
#         while True:
#
#
#     def handle(self, message: dict):
#         code = message.get('code', 0)
#         if code == STATUS.HANDSHAKE:
#             self.
#
#     def handle_shake(self, message: dict):