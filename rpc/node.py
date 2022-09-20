import copy
import json
import logging

from core.txmempool import TxMemPool
from node.gossip import Gossip
from rpc.grpcs import node_pb2_grpc
from rpc.grpcs import node_pb2
from core.block_chain import BlockChain
from threads.vote_center import VoteCenter

from utils import constant


class NodeService(node_pb2_grpc.NodeServicer):
    def get_node_status(self, request, context):
        bc = BlockChain()
        latest_block, _ = bc.get_latest_block()
        pool = TxMemPool()
        vote_center = VoteCenter()

        vote = copy.deepcopy(vote_center.vote)
        vote_str = json.dumps(vote)

        return node_pb2.StatusRespond(
            height=latest_block.height,
            vote_center_height=vote_center.height,
            pool_height=pool.height,
            pool_counts=pool.counts,
            gossip_queue=Gossip().queue_size,
            valid_txs=pool.valid_txs,
            vote_info=vote_str
        )

    def stop_node(self, request, context):
        constant.NODE_RUNNING = False
        return node_pb2.StopNodeRespond()

