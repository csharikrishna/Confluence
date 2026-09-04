"""
Forces safe storage defaults before any test module imports app/db_backend.

Incident: test_api.py and test_phase2_endpoints.py mock get_environmental_snapshot
and hit real /environment routes via TestClient, which triggers app.py's real
background-task persistence path (db_backend.save_snapshot). Neither file's
isolation is effective once a local .env sets STORAGE_BACKEND=mongo - app.py
calls through db_backend (not the storage module test_phase2_endpoints.py
patches), so those writes went straight to whatever real database MONGODB_URI
pointed at. Confirmed live: 31 rows of test-fixture data ended up in the
production Atlas cluster this way.

pytest imports conftest.py in a directory before collecting/importing any test
module in that directory, so setting these here - before environmental_data.py's
load_dotenv() ever runs - wins: python-dotenv's load_dotenv() defaults to
override=False, so it will not clobber a STORAGE_BACKEND already present in
os.environ. This forces the whole suite onto SQLite regardless of what any
developer's local .env has configured, without needing every test file to
remember to isolate storage correctly on its own.
"""

import os

os.environ["STORAGE_BACKEND"] = "sqlite"
os.environ.pop("MONGODB_URI", None)
