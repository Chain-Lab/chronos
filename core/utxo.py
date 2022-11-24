import copy
import logging

import pycouchdb.exceptions
from lru import LRU

from core.transaction import Transaction
from utils.leveldb import LevelDB
from utils.singleton import Singleton
from utils.funcs import pub_to_address
from utils.convertor import utxo_hash_to_db_key, addr_utxo_db_key, remove_utxo_db_prefix


class UTXOSet(Singleton):
    def __init__(self):
        self.db = LevelDB()
        self.__utxo_cache = LRU(5000)
        self.__address_cache = LRU(5000, callback=self.addr_cache_callback)

    def addr_cache_callback(self, key: str, value: list):
        self.db[key] = {"utxos": value}

    def reindex(self, bc):
        """
        更新数据库的UTXO， 将UTXO和链进行同步
        :param bc: Blockchain的实例
        """
        utxo_latest_db_key = utxo_hash_to_db_key("latest", 0)
        latest_block, prev_hash = bc.get_latest_block()
        insert_list = {}

        if not self.db[utxo_latest_db_key]:
            # 通过blockchain查询到未使用的交易
            utxos = bc.find_utxo()
            if not latest_block:
                return
            for tx_hash, index_vouts in utxos.items():

                for index_vout in index_vouts:
                    index = index_vout[0]
                    vout = index_vout[1]

                    vout_dict = vout.serialize()
                    utxo_db_key = utxo_hash_to_db_key(tx_hash, index)
                    vout_dict.update({
                        'hash': tx_hash,
                        'index': index
                    })
                    insert_list[utxo_db_key] = vout_dict
            try:
                self.db.batch_insert(insert_list)
            except pycouchdb.exceptions.Conflict as e:
                logging.error(e)
            self.set_latest_height(latest_block.block_header.height)
        else:
            latest_utxo_height = self.get_latest_height()
            latest_block_height = latest_block.block_header.height
            for i in range(latest_utxo_height, latest_block_height):
                block = bc.get_block_by_height(i)
                self.update(block)

    def set_latest_height(self, height):
        """
        设置本地UTXO的最新高度
        :param height: 需要设置的高度， 更新到数据库
        """
        utxo_latest_db_key = utxo_hash_to_db_key("latest", 0)
        self.db[utxo_latest_db_key] = {'height': height}

    def get_latest_height(self):
        utxo_latest_db_key = utxo_hash_to_db_key("latest", 0)
        utxo_latest_height_dict = self.db[utxo_latest_db_key]
        if utxo_latest_height_dict:
            return utxo_latest_height_dict['height']
        return 0

    def update(self, block):
        """
        更新数据库中的UTXO， 添加新的UTXO， 并且删除已被使用的UTXO
        """
        logging.debug("Update UTXO set.")
        insert_list = {}
        delete_list = []
        for tx in block.transactions:
            tx_hash = tx.tx_hash

            for idx, outputs in enumerate(tx.outputs):
                output_dict = outputs.serialize()
                output_dict["index"] = idx
                output_dict["tx_hash"] = tx_hash
                utxo_db_key = utxo_hash_to_db_key(tx_hash, idx)
                address = outputs.pub_key_hash
                address_db_key = addr_utxo_db_key(address)
                if address not in self.__address_cache:
                    self.find_utxo(address)
                self.__utxo_cache[utxo_db_key] = {
                    "tx_hash": tx_hash,
                    "output": output_dict,
                    "index": idx
                }
                self.__address_cache[address].add(utxo_db_key)
                insert_list[utxo_db_key] = copy.deepcopy(output_dict)
                insert_list[address_db_key] = list(self.__address_cache[address])

            for _input in tx.inputs:
                input_tx_hash = _input.tx_hash
                utxo_db_key = utxo_hash_to_db_key(input_tx_hash, _input.index)
                tx_hash_index_str = "{0}#{1}".format(tx_hash, _input.index)
                input_address = pub_to_address(_input.pub_key)
                address_db_key = addr_utxo_db_key(input_address)

                delete_list.append(utxo_db_key)

                self.__address_cache[input_address].discard(utxo_db_key)
                if utxo_db_key in self.__utxo_cache:
                    self.__utxo_cache.pop(utxo_db_key)
                insert_list[address_db_key] = {
                    "utxos": list(self.__address_cache[input_address])
                }
                logging.debug("UTxO {} cleaned.".format(tx_hash_index_str))

        self.db.batch_insert(insert_list)
        self.db.batch_remove(delete_list)

        self.set_latest_height(block.block_header.height)

    def roll_back(self, block, bc):
        """
        UTXO集合回滚逻辑， 遍历当前最高区块的交易进行回滚
        """
        insert_list = {}
        delete_list = []
        transaction: Transaction
        for transaction in block.transactions:
            tx_hash = transaction.tx_hash

            for idx, output in enumerate(transaction.outputs):
                utxo_db_key = utxo_hash_to_db_key(tx_hash, idx)

                address = output.pub_key_hash
                address_db_key = addr_utxo_db_key(address)
                delete_list.append(utxo_db_key)

                if address not in self.__address_cache:
                    self.find_utxo(address)
                self.__address_cache[address].discard(utxo_db_key)

                if utxo_db_key in self.__utxo_cache:
                    self.__utxo_cache.pop(utxo_db_key)
                insert_list[address_db_key] = {
                    "utxos": list(self.__address_cache[address])
                }

            if transaction.is_coinbase():
                continue

            for _input in transaction.inputs:
                input_tx_hash = _input.tx_hash
                output_index = _input.index
                utxo_db_key = utxo_hash_to_db_key(input_tx_hash, output_index)

                transaction = bc.get_transaction_by_tx_hash(tx_hash)
                outputs = transaction.outputs

                try:
                    output = outputs[output_index]
                except IndexError:
                    logging.error("Get output with index {} in tx#{} failed.".format(output_index, tx_hash))
                    continue
                output_dict = output.serialize()
                output_dict.update({'index': output_index})
                address = output_dict["pub_key_hash"]
                address_db_key = addr_utxo_db_key(address)
                tx_hash_index_str = "{0}#{1}".format(input_tx_hash, output_index)

                if address not in self.__address_cache:
                    self.find_utxo(address)
                self.__address_cache[address].add(utxo_db_key)
                self.__utxo_cache[utxo_db_key] = {
                    "tx_hash": tx_hash,
                    "output": output_dict,
                    "index": output_index
                }
                output_dict.update({"tx_hash": input_tx_hash})
                insert_list[utxo_db_key] = copy.deepcopy(output_dict)
                insert_list[address_db_key] = {
                    "utxos": list(self.__address_cache[address])
                }

        self.db.batch_insert(insert_list)
        self.db.batch_remove(delete_list)
        self.set_latest_height(block.block_header.height - 1)

    def find_utxo(self, address):
        # todo: leveldb 中如何检索
        """
        开放给openapi用于查询utxo的方法
        :param address: 需要查询的地址
        :return: 对应地址的utxo
        """
        address_db_key = addr_utxo_db_key(address)
        if address in self.__address_cache:
            utxos_db_key_set = self.__address_cache[address]
        else:
            utxos_db_key_set = self.db.get(address_db_key, {}).get("utxos", [])
            self.__address_cache[address] = set(utxos_db_key_set)

        utxos = {}
        for utxo_db_key in utxos_db_key_set:
            tx_hash_index_str = remove_utxo_db_prefix(utxo_db_key)
            if utxo_db_key in self.__utxo_cache:
                utxo = self.__utxo_cache[utxo_db_key]
            else:
                utxo = self.db.get(utxo_db_key, None)

                if utxo:
                    self.__utxo_cache[utxo_db_key] = utxo
                else:
                    logging.error("Get utxo error, get none from database.")

            flag_index = tx_hash_index_str.find("#")
            tx_hash = tx_hash_index_str[:flag_index]

            utxos[tx_hash] = utxo
        return utxos

    @staticmethod
    def clear_transactions(transactions):
        used_utxo = []
        txs = []
        for tx in transactions:
            for _input in tx.inputs:
                input_tx_hash = _input.tx_hash
                utxo = (input_tx_hash, _input.index)
                if utxo not in used_utxo:
                    used_utxo.append(utxo)
                    txs.append(tx)
        return txs


class FullTXOutput(object):
    def __init__(self, txid, txoutput, index):
        self.txid = txid
        self.txoutput = txoutput
        self.index = index
