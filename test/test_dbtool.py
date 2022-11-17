import unittest

from utils.leveldb import LevelDB


class TestDatabaseUtil(unittest.TestCase):

    def test_insert(self):
        db = LevelDB()

        insert_key = "test"
        insert_data = {"test": "testdata"}
        self.assertTrue(db.insert(insert_key, insert_data), "Database insert error.")

        data = db["test"]
        self.assertEqual(data, insert_data, "Get data from database not equal.")
        self.assertTrue(db.remove(insert_key), "Database delete error.")

    def test_delete(self):
        db = LevelDB()

        key = "delete_test"
        data = {"test": "delete"}
        self.assertTrue(db.insert(key, data), "Database insert error.")

        self.assertTrue(db.remove(key), "Database delete error.")
        self.assertEqual(db[key], None, "Get value from database with deleted key error.")

    def test_update(self):
        db = LevelDB()
        key = "test1"
        origin_data = {"test": "testdata"}
        new_data = {"test": "new testdata"}

        self.assertTrue(db.insert(key, origin_data), "Database insert error.")
        self.assertEqual(db[key], origin_data)
        self.assertTrue(db.insert(key, new_data), "Database insert error.")
        self.assertEqual(db[key], new_data)

        self.assertTrue(db.remove(key), "Database delete error.")

if __name__ == "__main__":
    unittest.main()
