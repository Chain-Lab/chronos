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

    # RPC 收到 broadcast 的响应函数
    async def rpc_broadcast(self, sender, nodeid, cprefix_len, message):
        source = Node(nodeid, sender[0], sender[1])

        self.welcome_if_new(source)
        await self.broadcast_message(message, cprefix_len + 1)
        return True

    async def call_broadcast(self, node_to_send, cprefix_len, message):
        address = (node_to_send.ip, node_to_send.port)
        result = await self.broadcast(address, self.source_node.id, cprefix_len, message)
        return self.handle_call_response(result, node_to_send)

    async def broadcast_message(self, message, start=0):
        for bucket_index in range(start, len(self.router.buckets)):
            bucket = self.router.buckets[bucket_index]

            if len(bucket) <= 0:
                continue

            node = bucket.select_node()
            await self.call_broadcast(node, bucket_index + 1, message)