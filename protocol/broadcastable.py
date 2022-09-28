import logging
import asyncio

from kademlia.protocol import KademliaProtocol
from kademlia.node import Node
from protocol.routing import RoutingTableV2

log = logging.getLogger(__name__)


class BroadcastableProtocol(KademliaProtocol):
    def __init__(self, source_node, storage, ksize):
        super().__init__(source_node, storage, ksize)
        self.router = RoutingTableV2(self, ksize, source_node)

    async def rpc_broadcast(self, sender, nodeid, cprefix_len, message):
        '''
        RPC 收到 broadcast 的响应函数
        :param sender: 发送者
        :param nodeid: 节点 id
        :param cprefix_len: 广播到达该节点的公共前缀长度
        :param message: 消息
        :return:
        '''
        source = Node(nodeid, sender[0], sender[1])

        self.welcome_if_new(source)

        # 从 cpl + 1 往下继续广播
        await self.broadcast_message(message, cprefix_len + 1)
        return True

    async def call_broadcast(self, node_to_send, cprefix_len, message):
        '''
        发送消息到其他节点
        :param node_to_send: 需要发送的节点
        :param cprefix_len: 当前广播的前缀长度位置
        :param message: 广播的消息
        :return:
        '''
        address = (node_to_send.ip, node_to_send.port)
        result = await self.broadcast(address, self.source_node.id, cprefix_len, message)
        return self.handle_call_response(result, node_to_send)

    async def broadcast_message(self, message, start=0):
        # 从cpl往后进行消息发送， 每个k桶随机选择节点
        for bucket_index in range(start, len(self.router.buckets)):
            bucket = self.router.buckets[bucket_index]

            if len(bucket) <= 0:
                continue

            node = bucket.select_node()
            await self.call_broadcast(node, bucket_index + 1, message)