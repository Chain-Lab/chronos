import threading
import logging
import grpc
from concurrent import futures

from rpc.grpcs import block_pb2_grpc
from rpc.grpcs import address_pb2_grpc
from rpc.grpcs import transaction_pb2_grpc
from rpc.block import BlockService
from rpc.address import AddressService
from rpc.transaction import TransactionService


class RPCServer(object):
    """
    暴露给服务器内部的RPC接口服务
    主要保证与其他模块进行解耦
    """

    def __init__(self):
        # 配置rpc服务的最大worker数量， 可以放入配置文件
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))

    def serve(self):
        # 注册rpc服务端子模块

        block_pb2_grpc.add_BlockServicer_to_server(BlockService(), self.server)
        address_pb2_grpc.add_AddressServicer_to_server(AddressService(), self.server)
        transaction_pb2_grpc.add_TransactionServicer_to_server(TransactionService(), self.server)

        # 配置rpc服务的端口， 可放入配置文件
        logging.debug("RPC server start on port 45555")
        self.server.add_insecure_port('[::]:45555')
        self.server.start()
        self.server.wait_for_termination()

    def start(self):
        thread = threading.Thread(target=self.serve, args=())
        thread.start()
