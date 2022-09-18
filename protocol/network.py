from kademlia.network import Server
from protocol.broadcastable import BroadcastableProtocol


class ServerV2(Server):
    protocol_class = BroadcastableProtocol

    def __init__(self, ksize=20, alpha=3, node_id=None, storage=None):
        super().__init__(ksize, alpha, node_id, storage)

    def _create_protocol(self):
        return self.protocol_class(self.node, self.storage, self.ksize)

    async def broadcast(self, message):
        await self.protocol.broadcast_message(message)
