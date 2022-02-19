import json

from couchdb import ResourceNotFound

from core.config import Config
from utils.dbutil import DBUtil
from core.block import Block
from core.merkle import MerkleTree
from core.block_header import BlockHeader
from core.utxo import UTXOSet
from core.transaction import Transaction


class BlockChain(object):

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
            raise IndexError('Index overflow')

    def add_new_block(self, transactions: list, vote: dict):
        latest_block, prev_hash = self.get_latest_block()
        height = latest_block.block_header.height + 1

        data = []
        for tx in transactions:
            data.append(json.dumps(tx.serialize()))
        merkle_tree = MerkleTree(data)
        block_header = BlockHeader(merkle_tree.root_hash, height, prev_hash)

        coin_base_tx = Transaction.coinbase_tx(vote)
        transactions.insert(coin_base_tx)

        # coinbase 钱包和节点耦合， 可以考虑将挖矿、钱包、全节点服务解耦
        # upd: 节点和挖矿耦合， 但是可以在配置中设置是否为共识节点
        txs = UTXOSet().clear_transactions(transactions)
        block = Block(block_header, txs)

        if not self.verify_block(block):
            pass
            # todo： 抛出交易验证失败错误

        block.set_header_hash()
        latest_hash = block.block_header.hash
        self.set_latest_hash(latest_hash)
        self.db.create(block.block_header.hash, block.serialize())

        UTXOSet().update(block)

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
            block = Block.deserialize(block_data)
        return block

    def get_block_by_hash(self, hash):
        data = self.db.get(hash)
        block = Block.deserialize(data)
        return block

    def get_transaction_by_txid(self, txid):
        """
        通过交易的txid来检索得到交易
        但是这里遍历区块的方式较为暴力， 需要进行优化
        在区块达到一定高度后可能存在一定的问题
        :param txid: 需要检索的交易id
        :return: 检索到交易返回交易， 否则返回None
        """
        latest_block, prev_hash = self.get_latest_block()
        latest_height = latest_block.block_header.height

        for height in range(latest_height, -1, -1):
            block = self.get_block_by_height(height)
            for tx in block.transactions:
                if tx.txid == txid:
                    return tx
        return None

    def add_block_from_peers(self, block):
        """
        从邻居节点接收到区块， 更新本地区块
        :param block:
        :return:
        """
        latest_block, prev_hash = self.get_latest_block()
        if latest_block:
            latest_height = latest_block.block_header.height
            if block.block_header.height < latest_height:
                # 从邻居节点收到的区块高度低于本地， 抛出错误
                raise ValueError('Block height error')
            if not self.verify_block(block):
                raise ValueError('Block invalid.')

            if block.block_header.height == latest_block and block != latest_block:
                UTXOSet().roll_back()
                self.roll_back()
            if block.block_header.height == latest_block + 1 and block.block_header.prev_block_hash == latest_block.block_header.hash:
                self.db.create(block.block_header.hash, block.serialize())
                latest_hash = block.block_header.hash
                self.set_latest_hash(latest_hash)
                UTXOSet().update(block)
        else:
            self.db.create(block.block_header.hash, block.serialize())
            last_hash = block.block_header.hash
            self.set_latest_hash(last_hash)
            UTXOSet().update(block)

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
            # todo: 错误显示方式fix
            print(e)
        block = self.get_block_by_height(latest_height - 1)
        self.set_latest_hash(block.block_header.hash)

    def find_utxo(self):
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
                txid = tx.txid

                for index, vout in enumerate(tx.vouts):
                    txos = spent_txos.get(txid, [])
                    if index in txos:
                        continue
                    old_vouts = unspent_txs.get(txid, [])
                    old_vouts.append([index, vout])
                    unspent_txs[tx.txid] = old_vouts

                if not tx.is_coinbase():
                    for vin in tx.vins:
                        vin_txid = vin.txid
                        txid_vouts = spent_txos.get(vin_txid, [])
                        if vin.vout not in txid_vouts:
                            txid_vouts.append(vin.vout)
                        spent_txos[vin_txid] = txid_vouts
        return unspent_txs

    def verify_block(self, block: Block):
        for tx in block.transactions:
            if not self.verify_transaction(tx):
                return False
        return True

    def verify_transaction(self, transaction: Transaction):
        prev_txs = {}
        for vin in transaction.vins:
            prev_tx = self.get_transaction_by_txid(vin.txid)
            if not prev_tx:
                continue
            prev_txs[prev_tx.txid] = prev_tx
        return transaction.verify(prev_txs)