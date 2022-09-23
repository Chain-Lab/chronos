import json
import logging
import threading
import time
from functools import lru_cache

import couchdb
from lru import LRU
import pycouchdb.exceptions
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
        self.__cache = LRU(30000)
        self.__block_cache = LRU(500)

        # 统计使用的变量， 和整体逻辑关系不大
        self.__cache_count_lock = threading.Lock()
        self.__block_count_lock = threading.Lock()

        self.__cache_used = 0
        self.__cache_hit = 0
        self.__block_used = 0
        self.__block_hit = 0

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
        latest_block, block_hash = self.get_latest_block()
        prev_height = latest_block.block_header.height
        height = latest_block.block_header.height + 1

        logging.debug("Vote info: {}".format(vote))

        coin_base_tx = Transaction.coinbase_tx(vote, delay_params)
        transactions.insert(0, coin_base_tx)

        data = []
        for tx in transactions:
            data.append(json.dumps(tx.serialize()))
        merkle_tree = MerkleTree(data)
        block_header = BlockHeader(merkle_tree.root_hash, height)

        # coinbase 钱包和节点耦合， 可以考虑将挖矿、钱包、全节点服务解耦
        # upd: 节点和挖矿耦合， 但是可以在配置中设置是否为共识节点
        txs = UTXOSet().clear_transactions(transactions)
        block = Block(block_header, txs)

        # upd:区块验证的逻辑放到Insert里面， 这里创建区块时不再进行区块的验证， 交易的验证在打包时即可完成
        # logging.debug("Start verify block.")
        # if not self.verify_block(block):
        #     logging.error("Block verify failed. Block struct: {}".format(block))
        #     return None

        # todo: 区块头的哈希是根据merkle树的根哈希值来进行哈希的， 和交易存在关系
        #  那么是否可以在区块中仅仅存入交易的哈希列表，交易的具体信息存在其他的表中以提高查询效率，区块不存储区块具体的信息？
        logging.debug("Get block#{} from database.".format(prev_height))
        prev_block = self.get_block_by_height(prev_height)

        if not prev_block:
            logging.debug("Prev block has been rolled back.")
            return None

        logging.debug("Set block hash with previous block.".format(prev_block.block_header.hash))
        block.set_header_hash(prev_block.block_header.hash)
        # logging.debug(block.serialize())
        # 先添加块再更新最新哈希， 避免添加区块时出现问题更新数据库
        # self.insert_block(block)
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

            self.insert_block(genesis_block)

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
        if height in self.__block_cache and self.__block_cache[height]:
            logging.debug("Hit height in cache, return block.")

            with self.__block_count_lock:
                self.__block_hit += 1
                self.__block_used += 1

            return self.__block_cache[height]
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
        self.__block_cache[height] = block

        with self.__block_count_lock:
            self.__block_used += 1

        return block

    # 缓存100个区块数据
    def get_block_by_hash(self, block_hash):
        if block_hash in self.__block_cache and self.__block_cache[block_hash]:
            logging.debug("Hit block hash in cache, return block.")

            with self.__block_count_lock:
                self.__block_hit += 1
                self.__block_used += 1

            return self.__block_cache[block_hash]

        if not block_hash or block_hash == "":
            return None

        data = self.db.get(block_hash)

        if not data:
            return None

        block = Block.deserialize(data)
        self.__block_cache[block_hash] = block

        with self.__block_count_lock:
            self.__block_used += 1

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
        if tx_hash in self.__cache:
            logging.debug("Hit cache, return result directly.")

            with self.__cache_count_lock:
                self.__cache_hit += 1
                self.__cache_used += 1

            return self.__cache[tx_hash]

        logging.debug("Search tx#{} in db".format(tx_hash))
        db_tx_key = "tx-" + tx_hash
        data = self.db.get(db_tx_key)

        with self.__cache_count_lock:
            self.__cache_used += 1

        try:
            tx = Transaction.deserialize(data)
            self.__cache[tx_hash] = tx
            return tx
        except:
            return None

    def roll_back(self):
        """
        回滚数据库中的latest记录， 将记录回滚到上一区块高度
        :return: None
        """
        latest_block, prev_hash = self.get_latest_block()
        latest_height = latest_block.block_header.height
        latest_hash = latest_block.block_header.hash

        # 先修改索引， 再删除数据， 尽量避免拿到空数据
        block = self.get_block_by_height(latest_height - 1)
        self.set_latest_hash(block.block_header.hash)

        if latest_hash in self.__block_cache:
            self.__block_cache.pop(latest_hash)

        if latest_height in self.__block_cache:
            self.__block_cache.pop(latest_height)

        delete_list = []

        for tx in latest_block.transactions:
            tx_hash = tx.tx_hash
            db_tx_key = "tx-" + tx_hash
            doc = self.db.get(db_tx_key)

            if doc:
                delete_list.append(doc)

            if tx_hash in self.__cache:
                self.__cache.pop(tx_hash)
            # try:
            #     self.db.delete(doc)
            # except ResourceNotFound as e:
            #     logging.error(e)
            # # 数据库中没有对应的交易信息
            # except TypeError as e:
            #     logging.error(e)

        doc = self.db.get(latest_block.block_header.hash)
        try:
            self.db.delete(doc)
        except ResourceNotFound as e:
            logging.error(e)

        try:
            self.db.batch_delete(delete_list)
        except pycouchdb.exceptions.Conflict as e:
            logging.error(e)
        except pycouchdb.exceptions.NotFound as e:
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
        for _input in transaction.inputs:
            tx_hash = _input.tx_hash
            prev_tx = self.get_transaction_by_tx_hash(tx_hash)

            if not prev_tx:
                return False
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
        height = block.block_header.height
        logging.info("Insert new block#{} height {}".format(block_hash, block.block_header.height))
        try:
            self.db.create(block_hash, block.serialize())
        except couchdb.http.ResourceConflict:
            return

        self.set_latest_hash(block_hash)
        UTXOSet().update(block)
        insert_list = []

        for tx in block.transactions:
            tx_hash = tx.tx_hash
            db_tx_key = "tx-" + tx_hash
            tx_dict = tx.serialize()
            tx_dict.update({"_id": db_tx_key})
            self.__cache[tx_hash] = tx
            insert_list.append(tx_dict)

        self.__block_cache[height] = block
        self.__block_cache[block_hash] = block

        try:
            self.db.batch_save(insert_list)
        except pycouchdb.exceptions.Conflict as e:
            logging.error(e)

    def get_cache_status(self):
        with self.__cache_count_lock:
            try:
                tx_cache_rate = round(self.__cache_hit / self.__cache_used, 3)
            except ZeroDivisionError:
                tx_cache_rate = 0

        with self.__block_count_lock:
            try:
                block_cache_rate = round(self.__block_hit / self.__block_used, 3)
            except ZeroDivisionError:
                block_cache_rate = 0

        return tx_cache_rate, block_cache_rate
