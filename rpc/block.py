import json

from core.block_chain import BlockChain
from rpc.grpcs import block_pb2
from rpc.grpcs import block_pb2_grpc


class BlockService(block_pb2_grpc.BlockServicer):
    """
    block相关的RPC服务端接口， 定义在protos/block.proto中
    """

    def get_block(self, request, context):
        """
        拉取区块， 可以指定高度、哈希， 或是直接获取最新区块
        :param request: 接收到的请求， 对应proto中定义的类型
        :param context:
        :return: None
        """
        request_type = request.type
        # todo: 校验传入的类型是否正确， 或是是否传入了类型
        #  在传入信息错误的情况下返回错误信息并写日志

        bc = BlockChain()
        block = None

        if request_type == block_pb2.HEIGHT:
            height = request.height
            block = bc.get_block_by_height(height)
        elif request_type == block_pb2.HASH:
            block_hash = request.hash
            block = bc.get_block_by_hash(block_hash)
        elif request_type == block_pb2.LATEST:
            block, _ = bc.get_latest_block()

        if block is not None:
            result = block.serialize()
        else:
            result = {}

        respond = block_pb2.BlockRespond(status=0, block=json.dumps(result))

        return respond
