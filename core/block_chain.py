import json
import logging
import time
from functools import lru_cache

import couchdb
from couchdb import ResourceNotFound

from core.block import Block
from core.block_header import BlockHeader
from core.config import Config
from core.merkle import MerkleTree
from core.transaction import Transaction
from core.utxo import UTXOSet
from utils.dbutil import DBUtil
from utils.singleton import Singleton


class BlockChain(Singleton):
    def __init__(self):
        db_url = Config().get('database.url')
        self.db = DBUtil(db_url)

    def __getitem__(self, index):
        """
        重写内部方法， 即blockchain[index]这个逻辑
        :param index:  需要取出的区块高度
        :return: None
        """
        latest_block, prev_hash = self.get_latest_block()
        height = -1
        if latest_block:
            height = latest_block.block_header.height

        if index <= height:
            return self.get_block_by_height(index)
        else:
            logging.warning("Index overflow while get block #{}".format(index))
            raise IndexError('Index overflow')

    def package_new_block(self, transactions: list, vote: dict, delay_params: dict):
        """
        新区块的产生逻辑， 传入待打包的交易列表和投票信息
        :param transactions:
        :param vote:
        :param delay_params:
        :return:
        """
        start_time = time.time()
        latest_block, prev_hash = self.get_latest_block()
        height = latest_block.block_header.height + 1

        logging.debug("Vote info: {}".format(vote))

        coin_base_tx = Transaction.coinbase_tx(vote, delay_params)
        transactions.insert(0, coin_base_tx)

        data = []
        for tx in transactions:
            data.append(json.dumps(tx.serialize()))
        merkle_tree = MerkleTree(data)
        block_header = BlockHeader(merkle_tree.root_hash, height, prev_hash)

        # coinbase 钱包和节点耦合， 可以考虑将挖矿、钱包、全节点服务解耦
        # upd: 节点和挖矿耦合， 但是可以在配置中设置是否为共识节点
        txs = UTXOSet().clear_transactions(transactions)
        block = Block(block_header, txs)

        logging.debug("Start verify block.")
        if not self.verify_block(block):
            logging.error("Block verify failed. Block struct: {}".format(block))
            return

        # todo: 区块头的哈希是根据merkle树的根哈希值来进行哈希的， 和交易存在关系
        #  那么是否可以在区块中仅仅存入交易的哈希列表，交易的具体信息存在其他的表中以提高查询效率，区块不存储区块具体的信息？
        block.set_header_hash()
        logging.debug(block.serialize())
        # 先添加块再更新最新哈希， 避免添加区块时出现问题更新数据库
        # self.insert_block(block)
        end_time = time.time()
        logging.debug("Package block use {}s".format(end_time - start_time))
        return block

    def new_genesis_block(self, transaction):
        """
        传入交易信息产生创世区块
        :param transaction: 创世区块包含的交易
        :return: None
        """
        if 'latest' not in self.db:
            transactions = [transaction]
            genesis_block = Block.new_genesis_block(transactions)
            genesis_block.set_header_hash()

            logging.info("Create genesis block : {}".format(genesis_block))

            # 更新顺序应该先创建区块再创建索引， 否则会出现获取为空的问题
            self.db.create(genesis_block.block_header.hash, genesis_block.serialize())
            self.set_latest_hash(genesis_block.block_header.hash)

            UTXOSet().update(genesis_block)

    def get_latest_block(self):
        """
        通过数据库中的记录latest来拉取得到区块
        :return: 返回Block对象和对应的哈希值
        """
        latest_block_hash_doc = self.db.get('latest')
        if not latest_block_hash_doc:
            return None, None

        latest_block_hash = latest_block_hash_doc.get('hash', '')
        block_data = self.db.get(latest_block_hash)
        # logging.debug(block_data)
        block = Block.deserialize(block_data)
        return block, latest_block_hash

    def set_latest_hash(self, hash):
        """
        设置最新区块的哈希值到数据库的latest记录中
        :param hash: 设置的哈希值
        :return: None
        """
        latest_hash = {
            "hash": str(hash)
        }

        if 'latest' not in self.db:
            self.db['latest'] = latest_hash
        else:
            latest_block_hash_doc = self.db.get('latest')
            latest_block_hash_doc.update(hash=hash)
            self.db.update([latest_block_hash_doc])

    def get_block_by_height(self, height):
        """
        通过高度获取区块
        :param height: 所需要获取的区块的高度
        """
        query = {
            "selector": {
                "block_header": {
                    "height": height
                }
            }
        }
        docs = self.db.find(query)
        block = None
        for block_data in docs:
            # logging.debug("Get block data: {}".format(block_data))
            block = Block.deserialize(block_data)
        return block

    # 缓存100个区块数据
    @lru_cache(maxsize=100)
    def get_block_by_hash(self, hash):
        data = self.db.get(hash)

        if hash == "" or not data:
            return None

        block = Block.deserialize(data)
        return block

    def get_transaction_by_tx_hash(self, tx_hash):
        """
        通过交易的tx_hash来检索得到交易
        但是这里遍历区块的方式较为暴力， 需要进行优化
        todo： 将交易的信息另外存入一个表？ 交易本身需要存入区块，可以直接存入表中，数据库直接建立索引
        在区块达到一定高度后可能存在一定的问题
        :param tx_hash: 需要检索的交易id
        :return: 检索到交易返回交易， 否则返回None
        """
        latest_block, block_hash = self.get_latest_block()
        block = latest_block

        while block:
            for tx in block.transactions:
                if tx.tx_hash == tx_hash:
                    return tx
            prev_hash = block.block_header.prev_block_hash
            logging.debug("Search tx in prev block#{}".format(prev_hash))
            block = self.get_block_by_hash(prev_hash)
        return None

    def roll_back(self):
        """
        回滚数据库中的latest记录， 将记录回滚到上一区块高度
        :return: None
        """
        latest_block, prev_hash = self.get_latest_block()
        latest_height = latest_block.block_header.height

        # 先修改索引， 再删除数据， 尽量避免拿到空数据
        block = self.get_block_by_height(latest_height - 1)
        self.set_latest_hash(block.block_header.hash)
        doc = self.db.get(latest_block.block_header.hash)
        try:
            self.db.delete(doc)
        except ResourceNotFound as e:
            logging.error(e)

    def find_utxo(self):
        """
        查找未被使用的utxo
        """
        spent_txos = {}
        unspent_txs = {}
        latest_block, prev_hash = self.get_latest_block()

        if latest_block:
            latest_height = latest_block.block_header.height
        else:
            latest_height = -1

        if latest_height == -1:
            return unspent_txs

        for height in range(latest_height, -1, -1):
            block = self.get_block_by_height(height)
            for tx in block.transactions:
                tx_hash = tx.tx_hash

                for idx, output in enumerate(tx.outputs):
                    txos = spent_txos.get(tx_hash, [])
                    if idx in txos:
                        continue
                    old_outputs = unspent_txs.get(tx_hash, [])
                    old_outputs.append([idx, output])
                    unspent_txs[tx.tx_hash] = old_outputs

                if not tx.is_coinbase():
                    for _input in tx.inputs:
                        input_tx_hash = _input.tx_hash
                        tx_hash_outputs = spent_txos.get(input_tx_hash, [])
                        if _input.index not in tx_hash_outputs:
                            tx_hash_outputs.append(_input.index)
                        spent_txos[input_tx_hash] = tx_hash_outputs
        return unspent_txs

    def verify_block(self, block: Block):
        """
        校验区块， 主要校验包含的交易的签名信息是否正确
        :param block: 待校验区块
        :return: 是否校验通过
        """
        start_time = time.time()
        for tx in block.transactions:
            if not self.verify_transaction(tx):
                end_time = time.time()
                logging.debug("Verify block use {} s.".format(end_time - start_time))
                return False
        end_time = time.time()
        logging.debug("Verify block use {} s.".format(end_time - start_time))
        return True

    def verify_transaction(self, transaction: Transaction):
        """
        校验交易， 在链上拉取到当前交易输入下的交易调用verify方法进行校验
        :param transaction: 待校验的交易
        :return: 是否校验通过
        """
        prev_txs = {}
        tx_cache = {}
        for _input in transaction.inputs:
            tx_hash = _input.tx_hash
            if tx_hash not in tx_cache.keys():
                # 优化： 先在cache里面查询， 如果没有的话再从数据库里面查询
                prev_tx = self.get_transaction_by_tx_hash(tx_hash)
                tx_cache[tx_hash] = prev_tx
            else:
                prev_tx = tx_cache[tx_hash]
            if not prev_tx:
                continue
            prev_txs[prev_tx.tx_hash] = prev_tx
        return transaction.verify(prev_txs)

    def get_latest_delay_params(self):
        latest_block, _ = self.get_latest_block()
        coinbase_tx_input = latest_block.transactions[0].inputs[0]
        return coinbase_tx_input.delay_params

    def insert_block(self, block: Block):
        """
        追加最新区块, 由单一的另外一个线程调用
        先更新区块， 再更新索引信息， 避免返回空区块
        @param block: 需要添加的区块
        @return:
        """
        block_hash = block.block_header.hash
        logging.info("Insert new block#{} height {}".format(block_hash, block.block_header.height))
        try:
            self.db.create(block_hash, block.serialize())
        except couchdb.http.ResourceConflict:
            return
        self.set_latest_hash(block_hash)
        UTXOSet().update(block)

