import json
import logging
import threading

from couchdb import ResourceNotFound, ResourceConflict

from core.block import Block
from core.block_header import BlockHeader
from core.config import Config
from core.merkle import MerkleTree
from core.transaction import Transaction
from core.utxo import UTXOSet
from utils.dbutil import DBUtil
from utils.singleton import Singleton


class BlockChain(Singleton):
    # upd: v1.1.2 修改为单例模式，减少初始化开销并添加一个线程用来维护区块

    def __init__(self):
        db_url = Config().get('database.url')
        self.db = DBUtil(db_url)
        # 线程处理的区块的cache，保存接收到的区块的哈希信息及高度，定期清除比较低的高度信息
        """
        cache的结构应该是:
        {
            hash(string): status(bool)
            表示哈希值对应的区块是否被线程处理过
        }
        """
        self.cache = {}

        self.__queue = []
        self.__cond = threading.Condition()
        self.thread = None

    def run(self):
        self.thread = threading.Thread(target=self.__task, args=())
        self.thread.start()

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

    def add_new_block(self, transactions: list, vote: dict, delay_params: dict):
        """
        新区块的产生逻辑， 传入待打包的交易列表和投票信息
        :param transactions:
        :param vote:
        :param delay_params:
        :return:
        """
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

        if not self.verify_block(block):
            logging.error("Block verify failed. Block struct: {}".format(block))
            return

        # todo: 区块头的哈希是根据merkle树的根哈希值来进行哈希的， 和交易存在关系
        #  那么是否可以在区块中仅仅存入交易的哈希列表，交易的具体信息存在其他的表中以提高查询效率，区块不存储区块具体的信息？
        block.set_header_hash()
        latest_hash = block.block_header.hash
        logging.debug(block.serialize())
        # 先添加块再更新最新哈希， 避免添加区块时出现问题更新数据库
        self.__insert_block(block)

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

            self.set_latest_hash(genesis_block.block_header.hash)
            self.db.create(genesis_block.block_header.hash, genesis_block.serialize())

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

    def get_block_by_hash(self, hash):
        data = self.db.get(hash)
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
        latest_block, prev_hash = self.get_latest_block()
        latest_height = latest_block.block_header.height

        for height in range(latest_height, -1, -1):
            block = self.get_block_by_height(height)
            for tx in block.transactions:
                if tx.tx_hash == tx_hash:
                    return tx
        return None

    def add_block_from_peers(self, block):
        """
        将区块添加到队列中， 添加之前检查一下在cache中是否存在
        :param block: 从邻居节点接收到的区块
        :return: None
        """
        block_hash = block.header_hash
        if block_hash in self.cache.keys():
            logging.info("Block#{} already in cache.".format(block_hash))
            return True

        with self.__cond:
            self.__queue.append(block)
            self.__cond.notify_all()
        return True

    def roll_back(self):
        """
        回滚数据库中的latest记录， 将记录回滚到上一区块高度
        :return: None
        """
        latest_block, prev_hash = self.get_latest_block()
        latest_height = latest_block.block_header.height
        doc = self.db.get(latest_block.block_header.hash)
        try:
            self.db.delete(doc)
        except ResourceNotFound as e:
            logging.error(e)
        # 回滚时没有查询到对应hash的记录， 原逻辑可以照常执行
        block = self.get_block_by_height(latest_height - 1)
        self.set_latest_hash(block.block_header.hash)

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
        for tx in block.transactions:
            if not self.verify_transaction(tx):
                return False
        return True

    def verify_transaction(self, transaction: Transaction):
        """
        校验交易， 在链上拉取到当前交易输入下的交易调用verify方法进行校验
        :param transaction: 待校验的交易
        :return: 是否校验通过
        """
        prev_txs = {}
        for _input in transaction.inputs:
            prev_tx = self.get_transaction_by_tx_hash(_input.tx_hash)
            if not prev_tx:
                continue
            prev_txs[prev_tx.tx_hash] = prev_tx
        return transaction.verify(prev_txs)

    def get_latest_delay_params(self):
        latest_block, _ = self.get_latest_block()
        coinbase_tx_input = latest_block.transactions[0].inputs[0]
        return coinbase_tx_input.delay_params

    def __insert_block(self, block: Block):
        """
        追加最新区块
        @param block: 需要添加的区块
        @return:
        """
        block_hash = block.block_header.hash
        logging.info("Insert new block#{} height {}".format(block_hash, block.block_header.height))
        self.db.create(block_hash, block)
        self.set_latest_hash(block_hash)
        UTXOSet().update(block)

    def __task(self):
        """
        区块信息处理线程的线程函数
        在队列中存在区块的时候进行处理
        @return:
        """
        while True:
            with self.__cond:
                while not len(self.__queue):
                    self.__cond.wait()
                block = self.__queue.pop()

                block_height = block.block_header.height
                block_hash = block.block_header.hash
                logging.debug("Pop block#{} from queue.".format(block_hash))

                latest_block, latest_hash = self.get_latest_block()
                latest_height = latest_block.block_header.height
                self.cache[block_hash] = True

                if not latest_block:
                    logging.info("Insert genesis block to database.")
                    self.__insert_block(block)
                    continue

                # 获取到的该区块的高度低于或等于本地高度， 说明区块已经存在
                if block_height <= latest_height:
                    logging.info("Block has equal block, check whether legal.")
                    block_count = block.vote_count
                    block_timestamp = block.block_header.timestamp

                    # 获取到本地存储的对等高度的区块
                    equal_block = self.get_block_by_height(block_height)
                    equal_count = equal_block.vote_count
                    equal_hash = equal_block.block_header.hash
                    equal_timestamp = block.block_header.timestamp
                    if block_hash == equal_hash or block_count < equal_count or (
                            block_count == equal_count and block_timestamp > equal_timestamp):
                        continue

                    # 如果代码逻辑到达这里， 说明需要进行区块的回退
                    rollback_times = latest_height - block_height
                    for _ in range(rollback_times):
                        latest_block, _ = self.get_latest_block()
                        logging.info("Rollback block#{}.".format(latest_block.block_header.hash))
                        UTXOSet().roll_back(latest_block)
                        self.roll_back()
                    self.__insert_block(block)
                    continue
                elif block_height == latest_height + 1:
                    # 取得区块的前一个区块哈希
                    block_prev_hash = block.block_header.prev_block_hash
                    if block_prev_hash == latest_hash:
                        self.__insert_block(block)
                    else:
                        # 最前面的区块没有被处理过， 将区块返回到队列中等待
                        if not self.cache[block_prev_hash]:
                            logging.debug("Block#{} push back to queue.".format(block_hash))
                            self.__queue.append(block)
                            self.cache[block_hash] = False
