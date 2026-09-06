"""
Unit and Integration Tests for User Authentication and API Key Management (auth.py & app.py)
"""

import os
import sys
import unittest
from fastapi.testclient import TestClient

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
import auth


class TestAuthModule(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_password_hashing(self):
        pwd = "SecureMarinePassword123!"
        hashed = auth.hash_password(pwd)
        self.assertIsInstance(hashed, str)
        self.assertTrue(hashed.startswith("$argon2id$"))
        self.assertTrue(auth.verify_password(pwd, hashed))
        self.assertFalse(auth.verify_password("WrongPassword", hashed))

        # Test backward-compatible verification for PBKDF2 600k hashes with prefix
        import base64
        import hashlib
        pbkdf2_salt = b"0123456789abcdef"
        pbkdf2_dk = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), pbkdf2_salt, 600000)
        pbkdf2_hash = f"$pbkdf2$600000${base64.b64encode(pbkdf2_salt + pbkdf2_dk).decode('ascii')}"
        self.assertTrue(auth.verify_password(pwd, pbkdf2_hash))
        self.assertFalse(auth.verify_password("WrongPassword", pbkdf2_hash))

        # Test backward-compatible verification for legacy un-prefixed 100,000-iteration hashes
        legacy_salt = b"0123456789abcdef"
        legacy_dk = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), legacy_salt, 100000)
        legacy_raw = base64.b64encode(legacy_salt + legacy_dk).decode("ascii")
        self.assertTrue(auth.verify_password(pwd, legacy_raw))
        self.assertFalse(auth.verify_password("WrongPassword", legacy_raw))

    def test_legacy_hash_upgrade_to_argon2id(self):
        import uuid
        import base64
        import hashlib
        import sqlite3
        import db_backend as storage

        unique_suffix = uuid.uuid4().hex[:8]
        email = f"legacy_{unique_suffix}@marine-test.org"
        pwd = "LegacyPassword123!"
        user_id = f"usr_{unique_suffix}"
        
        # Create a legacy PBKDF2 hash
        salt = b"0123456789abcdef"
        dk = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), salt, 100000)
        legacy_hash = base64.b64encode(salt + dk).decode("ascii")

        # Manually insert user with legacy hash
        if storage.BACKEND_NAME == "mongo":
            import mongo_storage
            db = mongo_storage._get_db()
            db.users.insert_one({
                "id": user_id,
                "email": email,
                "name": "Legacy User",
                "password_hash": legacy_hash,
                "created_at": "2025-01-01T00:00:00Z"
            })
        else:
            conn = sqlite3.connect(storage.DB_PATH, timeout=10)
            with conn:
                conn.execute(
                    "INSERT INTO users (id, email, name, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                    (user_id, email, "Legacy User", legacy_hash, "2025-01-01T00:00:00Z")
                )
            conn.close()

        # Authenticate with legacy password - should succeed and transparently upgrade
        auth_user, err = auth.authenticate_user(email, pwd)
        self.assertIsNone(err)
        self.assertIsNotNone(auth_user)

        # Verify that the stored hash in the database is now Argon2id!
        if storage.BACKEND_NAME == "mongo":
            import mongo_storage
            db = mongo_storage._get_db()
            u = db.users.find_one({"id": user_id})
            self.assertTrue(u["password_hash"].startswith("$argon2id$"))
        else:
            conn = sqlite3.connect(storage.DB_PATH, timeout=10)
            row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
            conn.close()
            self.assertTrue(row[0].startswith("$argon2id$"))

    def test_user_registration_and_auth(self):
        import uuid
        unique_suffix = uuid.uuid4().hex[:8]
        email = f"user_{unique_suffix}@marine-test.org"
        username = f"marine_{unique_suffix}"
        password = "Password123!"

        # Register user
        user, err = auth.register_user(email, username, password)
        self.assertIsNone(err)
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], email)
        self.assertEqual(user["name"], username)

        # Authenticate user with email
        auth_user, auth_err = auth.authenticate_user(email, password)
        self.assertIsNone(auth_err)
        self.assertIsNotNone(auth_user)
        self.assertEqual(auth_user["id"], user["id"])
        self.assertIn("token", auth_user)

        # Authenticate with wrong password
        wrong_auth, wrong_err = auth.authenticate_user(email, "BadPassword")
        self.assertIsNone(wrong_auth)
        self.assertIsNotNone(wrong_err)

        # Re-registration with same email should return error
        dup_user, dup_err = auth.register_user(email, f"other_{unique_suffix}", password)
        self.assertIsNone(dup_user)
        self.assertIsNotNone(dup_err)

    def test_api_key_lifecycle(self):
        import uuid
        unique_suffix = uuid.uuid4().hex[:8]
        email = f"keyuser_{unique_suffix}@marine-test.org"
        username = f"keyuser_{unique_suffix}"
        user, _ = auth.register_user(email, username, "Password123!")

        # Generate API key
        raw_key, key_record = auth.generate_api_key(user["id"], "Test Key")
        self.assertTrue(raw_key.startswith("conf_live_"))
        self.assertEqual(len(raw_key), 50)  # "conf_live_" + 40 hex chars
        self.assertEqual(key_record["label"], "Test Key")
        self.assertTrue(key_record["is_active"])

        # Validate API key
        validated_key = auth.validate_api_key(raw_key)
        self.assertIsNotNone(validated_key)
        self.assertEqual(validated_key["user_id"], user["id"])

        # Validate invalid key
        invalid_key = auth.validate_api_key("conf_live_invalidkey1234567890abcdef")
        self.assertIsNone(invalid_key)

        # List user keys (initial key + newly generated key = 2 keys)
        keys = auth.list_user_api_keys(user["id"])
        self.assertGreaterEqual(len(keys), 2)

        # Revoke key
        revoked = auth.revoke_api_key(user["id"], key_record["id"])
        self.assertTrue(revoked)

        # Validation should now fail
        val_after = auth.validate_api_key(raw_key)
        self.assertIsNone(val_after)

    def test_api_endpoints(self):
        import uuid
        unique_suffix = uuid.uuid4().hex[:8]
        email = f"endpoint_{unique_suffix}@marine-test.org"
        username = f"endpoint_{unique_suffix}"
        password = "EndpointPassword123!"

        # Register endpoint
        reg_res = self.client.post("/api/auth/register", json={
            "email": email,
            "username": username,
            "password": password
        })
        self.assertEqual(reg_res.status_code, 201)
        reg_data = reg_res.json()
        self.assertIn("session_token", reg_data)
        self.assertIn("initial_api_key", reg_data)
        self.assertTrue(reg_data["initial_api_key"]["raw_key"].startswith("conf_live_"))
        token = reg_data["session_token"]

        # Login endpoint
        login_res = self.client.post("/api/auth/login", json={
            "username_or_email": email,
            "password": password
        })
        self.assertEqual(login_res.status_code, 200)
        login_data = login_res.json()
        self.assertIn("session_token", login_data)

        # Me endpoint with valid token
        me_res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_res.status_code, 200)
        me_data = me_res.json()
        self.assertEqual(me_data["email"], email)
        self.assertGreaterEqual(len(me_data["api_keys"]), 1)

        # Me endpoint without token
        unauth_res = self.client.get("/api/auth/me")
        self.assertEqual(unauth_res.status_code, 401)

        # Generate new key via endpoint
        new_key_res = self.client.post("/api/auth/keys", 
            headers={"Authorization": f"Bearer {token}"},
            json={"key_name": "Secondary Key"}
        )
        self.assertEqual(new_key_res.status_code, 201)
        new_key_data = new_key_res.json()
        self.assertTrue(new_key_data["raw_key"].startswith("conf_live_"))
        key_id = new_key_data["key_id"]

        # Revoke key via endpoint
        del_res = self.client.delete(f"/api/auth/keys/{key_id}", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(del_res.status_code, 200)
        self.assertTrue(del_res.json().get("revoked"))

    def test_account_lockout_after_failed_logins(self):
        """Test brute-force protection: 5 failed logins triggers account lockout for 15 minutes."""
        import uuid
        unique_suffix = uuid.uuid4().hex[:8]
        email = f"lockout_{unique_suffix}@marine-test.org"
        pwd = "CorrectPassword123!"

        # Register user
        user, err = auth.register_user(email, f"user_{unique_suffix}", pwd)
        self.assertIsNone(err)

        # 5 consecutive bad password attempts
        for i in range(5):
            u, err = auth.authenticate_user(email, "WrongPassword!")
            self.assertIsNone(u)
            self.assertEqual(err, "Invalid email or password.")

        # 6th attempt should now be blocked by account lockout
        u, err = auth.authenticate_user(email, "WrongPassword!")
        self.assertIsNone(u)
        self.assertIn("Account temporarily locked", err)
        self.assertIn("consecutive failed attempts", err)

        # Even correct password should be rejected while locked
        u_correct, err_correct = auth.authenticate_user(email, pwd)
        self.assertIsNone(u_correct)
        self.assertIn("Account temporarily locked", err_correct)

        # Manually reset lockout to test recovery
        auth.reset_failed_logins(email)
        u_recovered, err_recovered = auth.authenticate_user(email, pwd)
        self.assertIsNone(err_recovered)
        self.assertIsNotNone(u_recovered)

    def test_mongo_sqlite_failover_for_auth_and_keys(self):
        """
        Verify that user accounts and API key management paths gracefully fall back
        to SQLite if MongoDB raises a mid-flow connection or query exception.
        """
        import uuid
        from unittest.mock import patch
        import db_backend as storage

        unique_suffix = uuid.uuid4().hex[:8]
        email = f"failover_{unique_suffix}@marine-test.org"
        name = f"failover_user_{unique_suffix}"
        pwd = "FailoverPassword123!"

        class BrokenMongoMock:
            def __getattr__(self, name):
                raise ConnectionError("Simulated mid-flight MongoDB socket disconnect")

        original_backend = storage.BACKEND_NAME
        try:
            # Force backend name to 'mongo' to trigger the Mongo branches
            storage.BACKEND_NAME = "mongo"

            with patch("mongo_storage._get_db", return_value=BrokenMongoMock()):
                # 1. Registration should gracefully fall back to SQLite
                user, err = auth.register_user(email, name, pwd)
                self.assertIsNone(err)
                self.assertIsNotNone(user)
                self.assertEqual(user["email"], email)

                # 2. Authentication should gracefully fall back to SQLite
                auth_u, auth_err = auth.authenticate_user(email, pwd)
                self.assertIsNone(auth_err)
                self.assertIsNotNone(auth_u)
                self.assertEqual(auth_u["id"], user["id"])

                # 3. API key generation should gracefully fall back to SQLite
                raw_key, key_record = auth.generate_api_key(user["id"], "Failover Key")
                self.assertTrue(raw_key.startswith("conf_live_"))
                self.assertEqual(key_record["label"], "Failover Key")

                # 4. API key validation should gracefully fall back to SQLite
                val = auth.validate_api_key(raw_key)
                self.assertIsNotNone(val)
                self.assertEqual(val["user_id"], user["id"])

                # 5. API key listing should gracefully fall back to SQLite
                keys = auth.list_user_api_keys(user["id"])
                self.assertGreaterEqual(len(keys), 1)

                # 6. API key revocation should gracefully fall back to SQLite
                revoked = auth.revoke_api_key(user["id"], key_record["id"])
                self.assertTrue(revoked)
                self.assertIsNone(auth.validate_api_key(raw_key))
        finally:
            storage.BACKEND_NAME = original_backend

    def test_cors_configuration_locked_down(self):
        """Verify CORS is locked down to explicit origins and disallows untrusted origins."""
        # Allowed origin
        res_allowed = self.client.options(
            "/api/auth/login",
            headers={
                "Origin": "http://localhost:8000",
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertEqual(res_allowed.status_code, 200)
        self.assertEqual(res_allowed.headers.get("access-control-allow-origin"), "http://localhost:8000")

        # Untrusted origin should NOT be echoed back as allowed
        res_evil = self.client.options(
            "/api/auth/login",
            headers={
                "Origin": "http://evil-attacker.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertNotEqual(res_evil.headers.get("access-control-allow-origin"), "http://evil-attacker.com")
        self.assertNotEqual(res_evil.headers.get("access-control-allow-origin"), "*")

    def test_duplicate_registration_race_prevention(self):
        """Verify DB-level uniqueness constraint prevents TOCTOU race on registration."""
        import uuid
        unique_suffix = uuid.uuid4().hex[:8]
        email = f"race_{unique_suffix}@marine-test.org"

        # First registration succeeds
        u1, err1 = auth.register_user(email, "User One", "Password123!")
        self.assertIsNone(err1)
        self.assertIsNotNone(u1)

        # Duplicate registration with identical email is rejected atomically
        u2, err2 = auth.register_user(email, "User Two", "OtherPassword456!")
        self.assertIsNone(u2)
        self.assertEqual(err2, "An account with this email already exists.")

    def test_nosql_injection_payloads_rejected(self):
        """Verify that dictionary/operator NoSQL injection payloads are safely rejected."""
        # 1. Dict payload in authenticate_user
        u, err = auth.authenticate_user({"$gt": ""}, "password")  # type: ignore
        self.assertIsNone(u)
        self.assertEqual(err, "Invalid email or password.")

        # 2. Operator prefix in authenticate_user
        u_op, err_op = auth.authenticate_user("$where: '1==1'", "password")
        self.assertIsNone(u_op)
        self.assertEqual(err_op, "Invalid email or password.")

        # 3. Dict payload in register_user
        reg_u, reg_err = auth.register_user({"$ne": None}, "Hacker", "password")  # type: ignore
        self.assertIsNone(reg_u)
        self.assertIn("Email must be a valid string", reg_err)

        # 4. Dict payload in get_user_by_id
        usr = auth.get_user_by_id({"$gt": ""})  # type: ignore
        self.assertIsNone(usr)

        # 5. Dict payload in validate_api_key
        val = auth.validate_api_key({"$ne": None})  # type: ignore
        self.assertIsNone(val)


if __name__ == "__main__":
    unittest.main()
