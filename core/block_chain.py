import json
import logging
import threading
import time
from functools import lru_cache

from lru import LRU

from core.block import Block
from core.block_header import BlockHeader
from core.config import Config
from core.merkle import MerkleTree
from core.transaction import Transaction
from core.utxo import UTXOSet
from utils.leveldb import LevelDB
from utils.singleton import Singleton
from utils.convertor import blockhash_to_db_key, tx_hash_to_db_key, utxo_hash_to_db_key, height_to_db_key


class BlockChain(Singleton):
    def __init__(self):
        self.db = LevelDB()
        self.__tx_cache = LRU(30000)
        self.__block_cache = LRU(500)

        # map block_height => block_hash
        self.__block_map = LRU(2000)

        # todo: init
        # 目前区块上的最新的区块， 只读
        self.__latest = None

        # 统计使用的变量， 和整体逻辑关系不大
        self.__cache_count_lock = threading.Lock()
        self.__block_count_lock = threading.Lock()

        self.__cache_used = 0
        self.__cache_hit = 0
        self.__block_used = 0
        self.__block_hit = 0

    def __getitem__(self, index) -> Block:
        """ 重写内部方法，通过索引获取区块

        根据高度获取某个指定的区块

        Args:
            index: 区块的高度

        Returns:
            目前本地的区块链下对应高度的区块

        Raises:
            IndexError: 在对应高度的区块不存在时返回
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

    def package_new_block(self,
                          transactions: list,
                          proof: dict,
                          delay_params: dict):
        """ 区块打包逻辑

        传入交易、投票、参数来打包新的区块
        获取上一个区块的信息后，生成新的区块头并包含传入的交易列表来生成新的区块

        Args:
            transactions: 交易列表
            proof: 共识节点证明
            delay_params: VDF参数

        Returns:
            打包得到的新区块
            如果上一个区块不存在，会返回None给调用的函数进行判断

        Raises:

        """
        latest_block, block_hash = self.get_latest_block()
        prev_height = latest_block.block_header.height
        height = latest_block.block_header.height + 1

        coin_base_tx = Transaction.coinbase_tx(proof, delay_params)
        transactions.insert(0, coin_base_tx)

        data = []
        for tx in transactions:
            data.append(json.dumps(tx.serialize()))
        merkle_tree = MerkleTree(data)
        block_header = BlockHeader(merkle_tree.root_hash, height)

        txs = UTXOSet().clear_transactions(transactions)
        block = Block(block_header, txs)

        # TODO(Decision): 区块头的哈希是根据merkle树的根哈希值来进行哈希的， 和交易存在关系
        #  那么是否可以在区块中仅仅存入交易的哈希列表，交易的具体信息存在其他的表中以提高查询效率，区块不存储区块具体的信息？
        logging.debug("Get block#{} from database.".format(prev_height))
        prev_block = self.get_block_by_height(prev_height)

        if not prev_block:
            logging.debug("Prev block has been rolled back.")
            return None

        logging.debug("Set block hash with previous block.".format(prev_block.block_header.hash))
        block.set_header_hash(prev_block.block_header.hash)
        # 先添加块再更新最新哈希， 避免添加区块时出现问题更新数据库
        return block

    def new_genesis_block(self, transaction: Transaction) -> None:
        """ 传入交易信息产生创世区块
        Args:
            transaction: 一般是第一笔coinbase交易
        """
        if self.db["latest"]:
            # 如果已经存在信息说明不需要生成创世区块
            return

        transactions = [transaction]
        genesis_block = Block.new_genesis_block(transactions)
        genesis_block.set_header_hash()

        logging.info("Create genesis block : {}".format(genesis_block))

        self.insert_block(genesis_block)

    def get_latest_block(self) -> (Block, str):
        """ 获取最新区块

        首先查询缓存的 __latest 变量是否存在区块，如果存在直接返回
        否则从数据库中得到最新区块的哈希值后再查找区块，最后返回
        Returns:
            目前本地存储的最新区块，如果不存在则直接返回
        """
        if self.__latest:
            block_hash = self.__latest.block_header.hash
            return self.__latest, block_hash

        latest_block_hash_obj = self.db["latest"]

        if not latest_block_hash_obj:
            return None, None

        latest_block_hash = latest_block_hash_obj.get("hash", "")
        block_db_key = blockhash_to_db_key(latest_block_hash)
        block_data = self.db[block_db_key]
        block = Block.deserialize(block_data)
        self.__latest = block
        return block, latest_block_hash

    def set_latest_hash(self, blockhash: str) -> None:
        """ 在数据库中设置最新区块的哈希值
        Args:
            blockhash: 对应的区块哈希值
        """
        latest_hash_dict = {
            "hash": blockhash
        }

        self.db["latest"] = latest_hash_dict

    def get_block_by_height(self, height: int):
        """ 获取指定高度的区块

        首先查询区块缓存中是否存在区块
          - 如果存在区块，获取缓存中对应的哈希值后，继续根据哈希值获取到区块
          - 如果区块不存在，从数据库中查询高度对应的区块的哈希值
        最后根据区块的哈希值去检索区块

        Args:
            height: 需要获取的区块的高度

        Returns:
            如果区块存在，返回对应高度下的区块，否则返回None

        """
        if self.__block_map.get(height, None):
            logging.debug("Hit height to hash cache, search block in cache...")

            block_hash = self.__block_map[height]
        else:
            block_height_db_key = height_to_db_key(height)
            block_hash = self.db[block_height_db_key]

            if not block_hash:
                return None

            self.__block_map[height] = block_hash

        return self.get_block_by_hash(block_hash)

    # 缓存100个区块数据
    def get_block_by_hash(self, block_hash: str):
        """ 根据区块哈希值获取区块

        首先根据哈希值检索缓存
          - 缓存命中，直接返回区块
          - 缓存不命中，根据区块哈希在数据库中检索区块数据
        如果区块不存在，返回空

        Args:
            block_hash: 区块哈希值
        Returns:
            查询区块成功的情况下返回一个区块
            如果区块不存在或哈希值字段不对则返回空
        """
        block_db_key = blockhash_to_db_key(block_hash)
        if block_hash in self.__block_cache and self.__block_cache[block_hash]:
            # 如果命中区块缓存，直接返回
            logging.debug("Hit block hash in cache, return block.")

            with self.__block_count_lock:
                self.__block_hit += 1
                self.__block_used += 1

            return self.__block_cache[block_hash]

        if not block_hash or block_hash == "":
            return None

        data = self.db[block_db_key]

        if not data:
            return None

        block = Block.deserialize(data)
        self.__block_cache[block_hash] = block

        with self.__block_count_lock:
            self.__block_used += 1

        return block

    def is_transaction_in_cache(self, tx_hash: str):
        """
        检查交易是否在 cache 中，用于 RPC 检查最近交易是否被打包
        Args:
            tx_hash: 交易的哈希
        Returns:
            bool 变量，如果存在则返回 True
        """
        return tx_hash in self.__tx_cache

    def get_transaction_by_tx_hash(self, tx_hash: str):
        """ 根据交易的哈希值获取交易
        Args:
            tx_hash: 需要获取的交易的哈希值
        Returns:
            和根据哈希值获取区块的逻辑类似
            首先查询缓存，在命中缓存的情况下直接返回
            如果检索失败直接返回空
        """
        if tx_hash in self.__tx_cache:
            logging.debug("Hit cache, return tx#{} directly.".format(tx_hash))

            with self.__cache_count_lock:
                self.__cache_hit += 1
                self.__cache_used += 1

            return self.__tx_cache[tx_hash]

        logging.debug("Search tx#{} in db".format(tx_hash))
        db_tx_key = tx_hash_to_db_key(tx_hash)
        data = self.db[db_tx_key]

        with self.__cache_count_lock:
            self.__cache_used += 1

        try:
            tx = Transaction.deserialize(data)
            self.__tx_cache[tx_hash] = tx
            return tx
        except Exception as e:
            return None

    def roll_back(self) -> None:
        """ 将区块链回滚一个高度

        回滚需要将状态退回到上一个区块的状态
          - 将所有当前最新区块的交易删除
        对 UTxO 的操作由 UTxOSet 中的 Rollback 函数来实现
        Returns: None
        """
        # 获取最新区块、最新高度和最新区块的哈希
        latest_block, prev_hash = self.get_latest_block()
        latest_height = latest_block.block_header.height
        latest_hash = latest_block.block_header.hash

        # 先修改索引， 再删除数据， 尽量避免拿到空数据
        block = self.get_block_by_height(latest_height - 1)
        self.__block_map.pop(latest_height)
        self.set_latest_hash(block.block_header.hash)
        self.__latest = block

        if latest_hash in self.__block_cache:
            self.__block_cache.pop(latest_hash)

        if latest_height in self.__block_cache:
            self.__block_cache.pop(latest_height)

        delete_list = []

        for tx in latest_block.transactions:
            tx_hash = tx.tx_hash
            tx_db_key = tx_hash_to_db_key(tx_hash)
            delete_list.append(tx_db_key)

            if tx_hash in self.__tx_cache:
                self.__tx_cache.pop(tx_hash)

        latest_block_hash = latest_block.block_header.hash
        latest_block_db_key = blockhash_to_db_key(latest_block_hash)
        self.db.remove(latest_block_db_key)
        self.db.batch_remove(delete_list)

    def find_utxo(self):
        """ 查找未被使用的utxo

        目前该函数的作用是返回所有未被使用的 UTxO
        但是好像没有被使用到，后面可以考虑删除
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
        """ 校验区块

        传入区块校验区块中的签名是否正确
        依次对交易的签名进行校验
        Args:
            block: 待校验区块
        Returns:
            所有交易校验成功则返回 True
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
        """ 校验交易

        在链上拉取到当前交易输入下的交易调用verify方法进行校验

        Args:
            transaction: 待校验的交易
        Returns:
            如果交易交易成功则返回 True
        """
        st = time.time()

        prev_txs = {}
        for _input in transaction.inputs:
            tx_hash = _input.tx_hash
            prev_tx = self.get_transaction_by_tx_hash(tx_hash)

            if not prev_tx:
                ed = time.time()
                logging.debug("Verify transaction use {} s.".format(ed - st))
                return False
            prev_txs[prev_tx.tx_hash] = prev_tx

        ed = time.time()
        logging.debug("Verify transaction use {} s.".format(ed - st))
        return transaction.verify(prev_txs)

    def get_latest_delay_params(self) -> dict:
        """ 获取 VDF 的最新计算参数

        首先拉取最新区块，然后获取到 VDF 的参数
        Returns:
            coinbase 交易中存在的 VDF 计算参数
        """
        latest_block, _ = self.get_latest_block()
        coinbase_tx_input = latest_block.transactions[0].inputs[0]
        return coinbase_tx_input.delay_params

    def insert_block(self, block: Block) -> None:
        """ 更新区块

        由 MergeThread 调用，将区块插入到数据库中，影响全局状态
        Attentions:
            注意先更新区块，再更新索引
        Args:
            block: 待插入的区块
        Returns: None
        """
        block_hash = block.block_header.hash
        block_db_key = blockhash_to_db_key(block_hash)
        block_height_db_key = height_to_db_key(block.height)
        height = block.block_header.height
        logging.info("Insert new block#{} height {}".format(block_hash, block.block_header.height))

        UTXOSet().update(block)
        insert_list = {block_db_key: block.serialize(), block_height_db_key: block_hash}

        for tx in block.transactions:
            tx_hash = tx.tx_hash
            db_tx_key = tx_hash_to_db_key(tx_hash)
            tx_dict = tx.serialize()
            self.__tx_cache[tx_hash] = tx
            insert_list[db_tx_key] = tx_dict

        self.set_latest_hash(block_hash)
        self.__latest = block
        self.__block_map[height] = block_hash
        self.__block_cache[block_hash] = block

        self.db.batch_insert(insert_list)

    def get_cache_status(self):
        """ 获取缓存命中情况

        由 RPC 调用，后续视情况删除
        """
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

    @property
    def latest_height(self):
        if not self.__latest:
            return -1
        else:
            return self.__latest.height