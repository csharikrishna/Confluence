"""
Tests for the storage backend selector (db_backend.py). Confirms the default
(no STORAGE_BACKEND set) resolves to storage.py's SQLite functions, and that
setting STORAGE_BACKEND=couchdb resolves to couchdb_storage.py's instead.

Reloads db_backend to re-run its module-level selection logic under different
env vars — always restored to the sqlite default in tearDown, since db_backend
is a shared singleton module that app.py/notifications.py also import; leaving
it pointed at couchdb would affect every other test in the session.
"""

import os
import sys
import importlib
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import storage
import couchdb_storage
import mongo_storage
import db_backend


class TestDbBackendSelector(unittest.TestCase):
    def tearDown(self):
        # Always leave the shared db_backend module back on the sqlite default,
        # regardless of test outcome, so later tests aren't affected.
        os.environ.pop("STORAGE_BACKEND", None)
        importlib.reload(db_backend)

    def test_default_backend_is_sqlite(self):
        self.assertEqual(db_backend.BACKEND_NAME, "sqlite")
        self.assertIs(db_backend.save_snapshot, storage.save_snapshot)
        self.assertIs(db_backend.DB_PATH, storage.DB_PATH)

    def test_couchdb_backend_selected_via_env_var(self):
        os.environ["STORAGE_BACKEND"] = "couchdb"
        importlib.reload(db_backend)

        self.assertEqual(db_backend.BACKEND_NAME, "couchdb")
        self.assertIs(db_backend.save_snapshot, couchdb_storage.save_snapshot)
        self.assertIs(db_backend.get_reading_hours_ago, couchdb_storage.get_reading_hours_ago)

    def test_mongo_backend_selected_via_env_var(self):
        os.environ["STORAGE_BACKEND"] = "mongo"
        importlib.reload(db_backend)

        self.assertEqual(db_backend.BACKEND_NAME, "mongo")
        self.assertIs(db_backend.save_snapshot, mongo_storage.save_snapshot)
        self.assertIs(db_backend.get_reading_hours_ago, mongo_storage.get_reading_hours_ago)

    def test_unrecognized_backend_falls_back_to_sqlite(self):
        os.environ["STORAGE_BACKEND"] = "something_else"
        importlib.reload(db_backend)
        self.assertEqual(db_backend.BACKEND_NAME, "something_else")
        # Falls back to sqlite functions since only "couchdb" switches away from it.
        self.assertIs(db_backend.save_snapshot, storage.save_snapshot)


if __name__ == "__main__":
    unittest.main()
