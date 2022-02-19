import couchdb

from utils.singleton import Singleton


class DBUtil(Singleton):
    def __init__(self, db_server, db_name='block_chain1'):
        self._db_server = db_server
        self._server = couchdb.Server(self._db_server)
        self._db_name = db_name
        self._db = None

    @property
    def db(self):
        if not self._db:
            try:
                self._db = self._server[self._db_name]
            except couchdb.ResourceNotFound:
                self._db = self._server.create(self._db_name)
        return self._db

    def create(self, id, data):
        self.db[id] = data
        return id

    def __getattr__(self, name):
        return getattr(self.db, name)

    def __contains__(self, name):
        return self.db.__contains__(name)

    def __getitem__(self, key):
        return self.db[key]

    def __setitem__(self, key, value):
        self.db[key] = value


if __name__ == "__main__":
    db = DBUtil('http://admin:couchdb2021chronos@172.26.0.8:5984')
    print(db.get('latest'))