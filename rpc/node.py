import binascii
import copy
import json
import logging

from core.transaction import Transaction
from core.txmempool import TxMemPool
from node.gossip import Gossip
from rpc.grpcs import node_pb2_grpc
from rpc.grpcs import node_pb2
from core.block_chain import BlockChain
from threads.vote_center import VoteCenter

from utils import constant, number_theory, funcs


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
            vote_info=vote_str,
            voted=vote_center.vote_address
        )

    def stop_node(self, request, context):
        p = number_theory.get_prime(512)
        q = number_theory.get_prime(512)
        n = p * q
        t = 100000

        delay_params = {
            "order": binascii.b2a_hex(n.to_bytes(
                length=(n.bit_length() + 7) // 8,
                byteorder='big',
                signed=False
            )).decode(),
            "time_param": t,
            # 在目前开发过程中设置为默认的256位随机数
            "seed": funcs.int2hex(number_theory.get_prime(256)),
            # 用于验证的参数， 节点计算的同时计算proof
            "verify_param": funcs.int2hex(number_theory.get_prime(256))
        }
        logging.debug(delay_params)

        bc = BlockChain()
        tx = Transaction.coinbase_tx({}, delay_params)
        bc.new_genesis_block(tx)
        return node_pb2.StopNodeRespond()

    def get_cache_status(self, request, context):
        bc = BlockChain()
        tx_hit_rate, block_hit_rate = bc.get_cache_status()
        return node_pb2.CacheStatusRespond(
            transaction_hit_rate=tx_hit_rate,
            block_hit_rate=block_hit_rate
        )