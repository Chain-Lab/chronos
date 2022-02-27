import logging

from couchdb import ResourceConflict, ResourceNotFound

from core.config import Config
from core.transaction import TxOutput
from utils.dbutil import DBUtil
from utils.singleton import Singleton


class UTXOSet(Singleton):
    FLAG = 'UTXO'

    def __init__(self):
        self.db = DBUtil(Config().get('database.url'))

    def reindex(self, bc):
        key = self.FLAG + 'latest'
        latest_block, prev_hash = bc.get_latest_block()

        if key not in self.db:
            utxos = bc.find_utxo()
            if not latest_block:
                return
            for tx_hash, index_vouts in utxos.items():
                key = self.FLAG + tx_hash

                for index_vout in index_vouts:
                    index = index_vout[0]
                    vout = index_vout[1]

                    vout_dict = vout.serialize()
                    vout_dict.update({'index': index})
                    tmp_key = key + '-' + str(index)
                    try:
                        self.db.create(tmp_key, vout_dict)
                    except ResourceConflict as e:
                        print(e)
            self.set_latest_height(latest_block.block_header.height)
        else:
            latest_utxo_height = self.get_latest_height()
            latest_block_height = latest_block.block_header.height
            for i in range(latest_utxo_height, latest_block_height):
                block = bc.get_block_by_height(i)
                self.update(block)

    def set_latest_height(self, height):
        key = self.FLAG + 'latest'
        if key not in self.db:
            latest_height_dict = {'height': height}
            self.db[key] = latest_height_dict
        else:
            latest_doc = self.db.get(key)
            latest_doc.update(height=height)
            self.db.update([latest_doc])

    def get_latest_height(self):
        key = self.FLAG + 'latest'
        if key in self.db:
            return self.db[key]['height']
        return 0

    def update(self, block):
        for tx in block.transactions:
            tx_hash = tx.tx_hash
            key = self.FLAG + tx_hash

            for idx, outputs in enumerate(tx.outputs):
                output_dict = outputs.serialize()
                output_dict.update({'index': idx})
                tmp_key = key + '-' + str(idx)
                try:
                    self.db.create(tmp_key, output_dict)
                except ResourceConflict as e:
                    print(e)

            for _input in tx.inputs:
                input_tx_hash = _input.tx_hash
                key = self.FLAG + input_tx_hash + '-' + str(_input.index)
                doc = self.db.get(key)

                if not doc:
                    continue
                try:
                    self.db.delete(doc)
                except ResourceConflict as e:
                    print(e)
        self.set_latest_height(block.block_header.height)

    def roll_back(self, block):
        for transaction in block.transactions:
            tx_hash = transaction.tx_hash
            key = self.FLAG + tx_hash

            for idx, output in enumerate(transaction.output):
                tmp_key = key + '-' + str(idx)
                doc = self.db.get(tmp_key)
                if not doc:
                    continue
                try:
                    self.db.delete(doc)
                except ResourceNotFound as e:
                    print(e)

            for _input in transaction.inputs:
                vin_tx_hash = _input.tx_hash
                output_index = _input.index
                key = self.FLAG + vin_tx_hash + '-' + str(output_index)
                query = {
                    "selector": {
                        "transactions": {
                            "$elemMatch": {
                                "tx_hash": vin_tx_hash
                            }
                        }
                    }
                }

                docs = self.db.find(query)
                if not docs:
                    doc = docs[0]
                else:
                    continue

                transactions = doc.get("transactions", [])
                # todo:命名规则变更, 原有代码中和外部循环变量一致
                for tx in transactions:
                    if tx.get('tx_hash', '') == tx_hash:
                        outputs = tx.get('outputs', [])
                        if len(outputs) <= output_index:
                            continue

                        vout = outputs[output_index]
                        vout_dict = vout.serialize()
                        vout_dict.update({'index': output_index})
                        tmp_key = key + '-' + str(output_index)

                        try:
                            self.db.create(tmp_key, vout_dict)
                        except ResourceConflict as e:
                            print(e)
        self.set_latest_height(block.block_header.height - 1)

    def find_utxo(self, address):
        """
        开放给openapi用于查询utxo的方法
        :param address: 需要查询的地址
        :return: 对应地址的utxo
        """
        query = {
            "selector": {
                "_id": {
                    "$regex": "^UTXO"
                },
                "pub_key_hash": address
            }
        }
        docs = self.db.find(query)
        utxos = []
        for doc in docs:
            index = doc.get('index', None)
            if index is None:
                continue
            doc_id = doc.id
            txid_index_str = doc_id.replace(self.FLAG, '')
            _flag_index = txid_index_str.find('-')
            txid = txid_index_str[:_flag_index]
            logging.debug("{}, {}, {}".format(txid_index_str, _flag_index, txid))
            utxos.append({
                "txid": txid,
                "output": doc,
                "index": index
            })
        return utxos

    @staticmethod
    def clear_transactions(transactions):
        used_utxo = []
        txs = []
        for tx in transactions:
            for vin in tx.vins:
                vin_txid = vin.txid
                utxo = (vin_txid, vin.vout)
                if utxo not in used_utxo:
                    used_utxo.append(utxo)
                    txs.append(tx)
        return txs


class FullTXOutput(object):
    def __init__(self, txid, txoutput, index):
        self.txid = txid
        self.txoutput = txoutput
        self.index = index