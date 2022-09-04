import couchdb
import pycouchdb

from utils.singleton import Singleton


class DBUtil(Singleton):
    def __init__(self, db_server, db_name='block_chain1'):
        self._db_server = db_server
        self._server = couchdb.Server(self._db_server)
        self._db_name = db_name
        self._db = None

        self.__bulk_server = pycouchdb.Server(self._db_server)
        self.__bulk_db = None

    @property
    def db(self):
        if not self._db:
            try:
                self._db = self._server[self._db_name]
                self.__bulk_db = self.__bulk_server.database(self._db_name)
            except couchdb.ResourceNotFound:
                self._db = self._server.create(self._db_name)
                self.__bulk_db = self.__bulk_server.database(self._db_name)
        return self._db

    def create(self, id, data):
        self.db[id] = data
        return id

    def batch_save(self, docs):
        self.__bulk_db: pycouchdb.client.Database
        result = self.__bulk_db.save_bulk(docs)
        return result

    def batch_delete(self, docs):
        self.__bulk_db: pycouchdb.client.Database
        result = self.__bulk_db.delete_bulk(docs)
        return result

    def __getattr__(self, name):
        return getattr(self.db, name)

    def __contains__(self, name):
        return self.db.__contains__(name)

    def __getitem__(self, key):
        return self.db[key]

    def __setitem__(self, key, value):
        self.db[key] = value
