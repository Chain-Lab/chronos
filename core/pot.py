import time

from core.config import Config
from utils.dbutil import DBUtil


class ProofOfTime(object):
    def __init__(self):
        db_url = Config().get('database.url')
        self.db = DBUtil(db_url)

    def local_vote(self):
        local_address = Config().get('node.address')
        local_time = time.time()

        final_address = ''
        final_time = 0
        abs_time = 1000

        wallets = self.db.get('wallets', '')

        for item in wallets.items():
            if '_id' in item or '_rev' in item or "" in item:
                continue

            item_address = item[0]
            if item_address == local_address:
                continue

            item_time = item[1].get('time')

            if abs(item_time - local_time) < abs_time:
                abs_time = abs(item_time - local_time)
                final_time = item_time
                final_address = item_address

        return final_address
