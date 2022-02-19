from utils.singleton import Singleton
from core.config import Config
from utils.dbutil import DBUtil

from couchdb import ResourceConflict, ResourceNotFound


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
            for txid, index_vouts in utxos.items():
                key = self.FLAG + txid

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
            latest_block_height = latest_utxo_height.block_header.height
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
            txid = tx.txid
            key = self.FLAG + txid

            for vout_index, vout in enumerate(tx.vouts):
                vout_dict = vout.serialize()
                vout_dict.update({'index': vout_index})
                tmp_key = key + '-' + str(vout_index)
                try:
                    self.db.create(tmp_key, vout_dict)
                except ResourceConflict as e:
                    print(e)

            for vin in tx.vins:
                vin_txid = vin.txid
                key = self.FLAG + vin_txid + '-' + str(vin.vout)
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
            txid = transaction.txud
            key = self.FLAG + txid

            for index, vout in enumerate(transaction.vouts):
                tmp_key = key + '-' + str(index)
                doc = self.db.get(tmp_key)
                if not doc:
                    continue
                try:
                    self.db.delete(doc)
                except ResourceNotFound as e:
                    print(e)

            for vin in transaction.vins:
                vin_txid = vin.txid
                vout_index = vin.vout
                key = self.FLAG + vin_txid + '-' + str(vin.vout)
                query = {
                    "selector": {
                        "transactions": {
                            "$elemMatch": {
                                "txid": vin_txid
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
                    if tx.get('txid', '') == txid:
                        vouts = tx.get('vouts', [])
                        if len(vouts) <= vout_index:
                            continue

                        vout = vouts[vout_index]
                        vout_dict = vout.serialize()
                        vout_dict.update({'index': vout_index})
                        tmp_key = key + '-' + str(vout_index)

                        try:
                            self.db.create(tmp_key, vout_dict)
                        except ResourceConflict as e:
                            print(e)
        self.set_latest_height(block.block_header.height - 1)

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
