import logging
import threading
from concurrent import futures

import grpc

from rpc.address import AddressService
from rpc.block import BlockService
from rpc.grpcs import address_pb2_grpc
from rpc.grpcs import block_pb2_grpc
from rpc.grpcs import transaction_pb2_grpc
from rpc.grpcs import node_pb2_grpc
from rpc.transaction import TransactionService
from rpc.node import NodeService


class RPCServer(object):
    """
    暴露给服务器内部的RPC接口服务
    主要保证与其他模块进行解耦
    """

    def __init__(self):
        # RPC 单次消息传输限制 2^29 = 512MB
        message_max_size = 2 ** 29

        # 配置rpc服务的最大worker数量， 可以放入配置文件
        self.server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=20),
            options=[
                ('grpc.max_send_message_length', message_max_size),
                ('grpc.max_receive_message_length', message_max_size)
            ])

    def serve(self):
        # 注册rpc服务端子模块

        block_pb2_grpc.add_BlockServicer_to_server(BlockService(), self.server)
        address_pb2_grpc.add_AddressServicer_to_server(AddressService(), self.server)
        transaction_pb2_grpc.add_TransactionServicer_to_server(TransactionService(), self.server)
        node_pb2_grpc.add_NodeServicer_to_server(NodeService(), self.server)

        # 配置rpc服务的端口， 可放入配置文件
        logging.debug("RPC server start on port 45555")
        self.server.add_insecure_port('[::]:45555')
        self.server.start()
        self.server.wait_for_termination()

    def start(self):
        thread = threading.Thread(target=self.serve, args=())
        thread.start()
