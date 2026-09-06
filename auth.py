"""
Authentication & API Key Management Module for Confluence
Supports user registration, secure credential hashing, session tokens,
and developer Confluence API Key generation (conf_live_...).

Compatible with both SQLite (storage.py) and MongoDB (mongo_storage.py).
"""

import os
import time
import hmac
import uuid
import base64
import json
import secrets
import hashlib
import sqlite3
import threading
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

import db_backend as storage

logger = logging.getLogger("environmental_api.auth")
AUTH_SECRET = os.getenv("CONFLUENCE_AUTH_SECRET", "confluence_marine_intel_secret_key_2026")
TOKEN_EXPIRY_HOURS = 72

# Account Lockout Thresholds
# Architectural Tradeoff Note:
# Hard account lockout (15 minutes after 5 failed attempts per email) prevents raw
# credential stuffing against user accounts, but introduces a known denial-of-service (DoS)
# risk where an adversary with a known victim email can lock the legitimate user out.
# Production evolution paths include per-IP exponential backoff, proof-of-work/CAPTCHA,
# or email-based magic unlock links. For the current deployment stage, this hard lockout
# combined with slowapi per-IP rate limiting (5 req/min on /login) balances brute-force defense.
MAX_FAILED_LOGINS = 5
LOCKOUT_DURATION_SECONDS = 900  # 15 minutes

_failed_login_attempts: Dict[str, List[float]] = {}
_lockout_lock = threading.Lock()


def is_account_locked(email: str) -> Tuple[bool, int]:
    """
    Checks if an email is temporarily locked due to repeated failed logins.
    Returns (is_locked, seconds_remaining).
    """
    email_clean = email.strip().lower()
    now = time.time()
    with _lockout_lock:
        attempts = _failed_login_attempts.get(email_clean, [])
        recent_attempts = [t for t in attempts if now - t < LOCKOUT_DURATION_SECONDS]
        _failed_login_attempts[email_clean] = recent_attempts
        if len(recent_attempts) >= MAX_FAILED_LOGINS:
            earliest = recent_attempts[0]
            remaining = int(LOCKOUT_DURATION_SECONDS - (now - earliest))
            return True, max(1, remaining)
        return False, 0


def record_failed_login(email: str):
    """Records a failed login attempt for an email."""
    email_clean = email.strip().lower()
    now = time.time()
    with _lockout_lock:
        if email_clean not in _failed_login_attempts:
            _failed_login_attempts[email_clean] = []
        _failed_login_attempts[email_clean].append(now)


def reset_failed_logins(email: str):
    """Resets failed login tracking for an email after successful authentication."""
    email_clean = email.strip().lower()
    with _lockout_lock:
        _failed_login_attempts.pop(email_clean, None)


# -----------------------------------------------------------------------------
# Database Schema Initialization
# -----------------------------------------------------------------------------
def init_auth_db():
    """Initializes tables for users and API keys in SQLite and collections in Mongo."""
    if storage.BACKEND_NAME == "mongo":
        try:
            import mongo_storage
            db = mongo_storage._get_db()
            if db is not None:
                db.users.create_index("email", unique=True)
                db.api_keys.create_index("key_hash", unique=True)
                db.api_keys.create_index("user_id")
        except Exception as e:
            logger.warning(f"Mongo auth schema init failed ({e}); SQLite failover will be used.")

    # Always ensure SQLite tables exist so failover is instantaneous if Mongo drops
    conn = sqlite3.connect(storage.DB_PATH, timeout=10)
    try:
        with conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS api_keys (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    key_hash TEXT UNIQUE NOT NULL,
                    key_prefix TEXT NOT NULL,
                    label TEXT NOT NULL,
                    tier TEXT NOT NULL DEFAULT 'developer',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);")
    finally:
        conn.close()


init_auth_db()


# -----------------------------------------------------------------------------
# Password & Token Helpers (Argon2id + PBKDF2 Legacy Compatibility)
# -----------------------------------------------------------------------------
# OWASP Tier-1 Standard: Argon2id (memory_cost=65536, time_cost=3, parallelism=4)
_argon2_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)
PBKDF2_ROUNDS = 600000
LEGACY_PBKDF2_ROUNDS = 100000


def hash_password(password: str) -> str:
    """Hashes password using state-of-the-art OWASP Argon2id."""
    return _argon2_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """
    Verifies a password against the stored hash.
    Supports:
    1. Modern Argon2id ($argon2id$...)
    2. Modern PBKDF2-SHA256 ($pbkdf2$<rounds>$<payload>)
    3. Legacy PBKDF2-SHA256 (raw base64 salt+dk, 100k rounds)
    """
    if not hashed or not password:
        return False

    try:
        if hashed.startswith("$argon2id$") or hashed.startswith("$argon2"):
            try:
                return _argon2_hasher.verify(hashed, password)
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                return False

        if hashed.startswith("$pbkdf2$"):
            parts = hashed.split("$")
            iterations = int(parts[2])
            raw = base64.b64decode(parts[3].encode("ascii"))
            salt = raw[:16]
            expected_dk = raw[16:]
            actual_dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
            return hmac.compare_digest(expected_dk, actual_dk)

        # Legacy raw base64 PBKDF2 (100k rounds)
        raw = base64.b64decode(hashed.encode("ascii"))
        salt = raw[:16]
        expected_dk = raw[16:]
        actual_dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, LEGACY_PBKDF2_ROUNDS)
        return hmac.compare_digest(expected_dk, actual_dk)
    except Exception:
        return False


# Precomputed dummy hash for constant-time evaluation against nonexistent users
_DUMMY_TIMING_HASH = hash_password("confluence_timing_mitigation_pad_salt_2026")


def create_session_token(user_id: str, email: str) -> str:
    """Creates a signed session token containing user payload and expiration."""
    exp = int(time.time()) + (TOKEN_EXPIRY_HOURS * 3600)
    payload = {"uid": user_id, "email": email, "exp": exp}
    payload_json = json.dumps(payload, separators=(",", ":"))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode("utf-8")).decode("ascii").rstrip("=")
    sig = hmac.new(AUTH_SECRET.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_session_token(token: str) -> Optional[Dict[str, Any]]:
    """Verifies and decodes a session token. Returns payload dict or None."""
    if not token or "." not in token:
        return None
    try:
        payload_b64, sig = token.split(".", 1)
        expected_sig = hmac.new(AUTH_SECRET.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None

        # Add padding back if necessary
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
        if payload.get("exp", 0) < int(time.time()):
            return None  # Expired
        return payload
    except Exception:
        return None


# -----------------------------------------------------------------------------
# Input Sanitization & NoSQL Injection Defense
# -----------------------------------------------------------------------------
def _sanitize_string_input(val: Any, field_name: str = "Input") -> str:
    """
    Enforces strict string typing and prevents NoSQL query injection.
    Rejects non-string payloads (e.g. dicts like {'$gt': ''}, lists),
    bracketed expressions, and operator prefixes.
    """
    if not isinstance(val, str):
        raise ValueError(f"{field_name} must be a valid string, got {type(val).__name__}.")
    val_clean = val.strip()
    if val_clean.startswith("$") or "{" in val_clean or "}" in val_clean:
        raise ValueError(f"Invalid characters or NoSQL query operator detected in {field_name}.")
    return val_clean


# -----------------------------------------------------------------------------
# User Account Operations
# -----------------------------------------------------------------------------
def register_user(email: str, name: str, password: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Registers a new user with atomic DB-level unique constraints (preventing TOCTOU race
    conditions on duplicate registration) and Mongo -> SQLite failover.
    Returns (user_dict, error_string).
    """
    try:
        email_clean = _sanitize_string_input(email, "Email").lower()
        name_clean = _sanitize_string_input(name, "Name")
        pwd_clean = _sanitize_string_input(password, "Password")
    except ValueError as ve:
        return None, str(ve)

    if not email_clean or "@" not in email_clean:
        return None, "A valid email address is required."
    if len(pwd_clean) < 6:
        return None, "Password must be at least 6 characters."

    pwd_hash = hash_password(pwd_clean)
    user_id = "usr_" + uuid.uuid4().hex[:12]
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    user_persisted = False
    if storage.BACKEND_NAME == "mongo":
        try:
            import mongo_storage
            db = mongo_storage._get_db()
            if db is not None:
                user_doc = {
                    "id": user_id,
                    "email": email_clean,
                    "name": name_clean,
                    "password_hash": pwd_hash,
                    "created_at": now_iso,
                }
                db.users.insert_one(user_doc)
                user_persisted = True
        except Exception as e:
            err_str = str(e).lower()
            if "duplicate key" in err_str or "e11000" in err_str:
                return None, "An account with this email already exists."
            logger.warning(f"Mongo register_user failed ({e}), falling back to SQLite.")

    if not user_persisted:
        conn = sqlite3.connect(storage.DB_PATH, timeout=10)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO users (id, email, name, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                    (user_id, email_clean, name_clean, pwd_hash, now_iso),
                )
        except sqlite3.IntegrityError:
            return None, "An account with this email already exists."
        finally:
            conn.close()

    # Automatically generate an initial starter API key for the new developer
    initial_key, _ = generate_api_key(user_id, "Default Starter Key")

    return {
        "id": user_id,
        "email": email_clean,
        "name": name_clean,
        "created_at": now_iso,
        "initial_api_key": initial_key,
    }, None


def authenticate_user(email: str, password: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Authenticates email + password with brute-force lockout, NoSQL injection guard, and Mongo -> SQLite failover."""
    try:
        email_clean = _sanitize_string_input(email, "Email").lower()
        pwd_clean = _sanitize_string_input(password, "Password")
    except ValueError:
        # Constant-time dummy verification on invalid inputs
        verify_password("invalid", _DUMMY_TIMING_HASH)
        return None, "Invalid email or password."

    # 1. Check account lockout
    locked, remaining_secs = is_account_locked(email_clean)
    if locked:
        remaining_mins = max(1, round(remaining_secs / 60))
        return None, f"Account temporarily locked due to {MAX_FAILED_LOGINS} consecutive failed attempts. Please wait {remaining_mins} minutes."

    user = None
    if storage.BACKEND_NAME == "mongo":
        try:
            import mongo_storage
            db = mongo_storage._get_db()
            if db is not None:
                user = db.users.find_one({"email": email_clean})
        except Exception as e:
            logger.warning(f"Mongo authenticate_user query failed ({e}), falling back to SQLite.")
            user = None

    if not user:
        conn = sqlite3.connect(storage.DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email_clean,)).fetchone()
            if row:
                user = dict(row)
        finally:
            conn.close()

    if not user:
        # Constant-time dummy verification to eliminate side-channel user enumeration
        verify_password(password, _DUMMY_TIMING_HASH)
        record_failed_login(email_clean)
        return None, "Invalid email or password."

    if not verify_password(password, user["password_hash"]):
        record_failed_login(email_clean)
        return None, "Invalid email or password."

    # Successful authentication — reset failed login tracking
    reset_failed_logins(email_clean)

    # Transparently upgrade legacy PBKDF2 hashes to modern Argon2id on successful login
    if not user["password_hash"].startswith("$argon2id$"):
        new_hash = hash_password(password)
        try:
            if storage.BACKEND_NAME == "mongo":
                import mongo_storage
                db = mongo_storage._get_db()
                if db is not None:
                    db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": new_hash}})
            else:
                conn = sqlite3.connect(storage.DB_PATH, timeout=10)
                with conn:
                    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user["id"]))
                conn.close()
        except Exception as e:
            logger.warning(f"Hash upgrade to Argon2id deferred: {e}")

    token = create_session_token(user["id"], user["email"])
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "token": token,
    }, None


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Fetches user details by user ID with NoSQL injection guard and Mongo -> SQLite failover."""
    try:
        clean_uid = _sanitize_string_input(user_id, "User ID")
    except ValueError:
        return None

    if storage.BACKEND_NAME == "mongo":
        try:
            import mongo_storage
            db = mongo_storage._get_db()
            if db is not None:
                u = db.users.find_one({"id": clean_uid})
                if u:
                    return {"id": u["id"], "email": u["email"], "name": u["name"], "created_at": u["created_at"]}
        except Exception as e:
            logger.warning(f"Mongo get_user_by_id failed ({e}), falling back to SQLite.")

    conn = sqlite3.connect(storage.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT id, email, name, created_at FROM users WHERE id = ?", (clean_uid,)).fetchone()
        if row:
            return dict(row)
    finally:
        conn.close()
    return None


# -----------------------------------------------------------------------------
# Confluence API Key Management (conf_live_...)
# -----------------------------------------------------------------------------
def generate_api_key(user_id: str, label: str = "Default API Key") -> Tuple[str, Dict[str, Any]]:
    """
    Generates a new secure Confluence API key in the format `conf_live_<hex>`.
    Stores the SHA-256 hash in the database with Mongo -> SQLite failover.
    The raw key is returned ONCE upon generation for the user to copy.
    """
    try:
        clean_uid = _sanitize_string_input(user_id, "User ID")
        label_clean = _sanitize_string_input(label or "Default API Key", "Label")
    except ValueError as ve:
        raise ValueError(f"Invalid API key generation parameters: {ve}")

    raw_key = "conf_live_" + secrets.token_hex(20)
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    key_prefix = f"conf_live_{raw_key[10:14]}...{raw_key[-4:]}"
    key_id = "key_" + uuid.uuid4().hex[:10]
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    key_record = {
        "id": key_id,
        "user_id": clean_uid,
        "key_prefix": key_prefix,
        "label": label_clean,
        "tier": "developer",
        "is_active": True,
        "created_at": now_iso,
        "last_used_at": None,
    }

    key_persisted = False
    if storage.BACKEND_NAME == "mongo":
        try:
            import mongo_storage
            db = mongo_storage._get_db()
            if db is not None:
                doc = dict(key_record)
                doc["key_hash"] = key_hash
                doc["is_active"] = 1
                db.api_keys.insert_one(doc)
                key_persisted = True
        except Exception as e:
            logger.warning(f"Mongo generate_api_key failed ({e}), falling back to SQLite.")

    if not key_persisted:
        conn = sqlite3.connect(storage.DB_PATH, timeout=10)
        try:
            with conn:
                conn.execute(
                    """INSERT INTO api_keys (id, user_id, key_hash, key_prefix, label, tier, is_active, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (key_id, clean_uid, key_hash, key_prefix, label_clean, "developer", 1, now_iso),
                )
        finally:
            conn.close()

    return raw_key, key_record


def list_user_api_keys(user_id: str) -> List[Dict[str, Any]]:
    """Returns all active and inactive API keys for a given user with NoSQL guard and Mongo -> SQLite failover."""
    try:
        clean_uid = _sanitize_string_input(user_id, "User ID")
    except ValueError:
        return []

    keys = []
    if storage.BACKEND_NAME == "mongo":
        try:
            import mongo_storage
            db = mongo_storage._get_db()
            if db is not None:
                cursor = db.api_keys.find({"user_id": clean_uid}).sort("created_at", -1)
                for k in cursor:
                    keys.append({
                        "id": k["id"],
                        "key_prefix": k["key_prefix"],
                        "label": k["label"],
                        "tier": k.get("tier", "developer"),
                        "is_active": bool(k.get("is_active", 1)),
                        "created_at": k["created_at"],
                        "last_used_at": k.get("last_used_at"),
                    })
                return keys
        except Exception as e:
            logger.warning(f"Mongo list_user_api_keys failed ({e}), falling back to SQLite.")

    conn = sqlite3.connect(storage.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, key_prefix, label, tier, is_active, created_at, last_used_at FROM api_keys WHERE user_id = ? ORDER BY created_at DESC",
            (clean_uid,),
        ).fetchall()
        for r in rows:
            k = dict(r)
            k["is_active"] = bool(k["is_active"])
            keys.append(k)
    finally:
        conn.close()
    return keys


def revoke_api_key(user_id: str, key_id: str) -> bool:
    """Revokes (deactivates) an API key owned by the user with NoSQL guard and Mongo -> SQLite failover."""
    try:
        clean_uid = _sanitize_string_input(user_id, "User ID")
        clean_kid = _sanitize_string_input(key_id, "Key ID")
    except ValueError:
        return False

    if storage.BACKEND_NAME == "mongo":
        try:
            import mongo_storage
            db = mongo_storage._get_db()
            if db is not None:
                res = db.api_keys.update_one({"id": clean_kid, "user_id": clean_uid}, {"$set": {"is_active": 0}})
                if res.modified_count > 0:
                    return True
        except Exception as e:
            logger.warning(f"Mongo revoke_api_key failed ({e}), falling back to SQLite.")

    conn = sqlite3.connect(storage.DB_PATH, timeout=10)
    try:
        with conn:
            cur = conn.execute("UPDATE api_keys SET is_active = 0 WHERE id = ? AND user_id = ?", (clean_kid, clean_uid))
            return cur.rowcount > 0
    finally:
        conn.close()


def validate_api_key(raw_key: str) -> Optional[Dict[str, Any]]:
    """
    Validates an incoming API key string with NoSQL guard and Mongo -> SQLite failover.
    If valid and active, updates `last_used_at` and returns the key record. Otherwise returns None.
    """
    if not isinstance(raw_key, str) or not raw_key.startswith("conf_live_"):
        return None
    try:
        clean_key = _sanitize_string_input(raw_key, "API Key")
    except ValueError:
        return None

    key_hash = hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if storage.BACKEND_NAME == "mongo":
        try:
            import mongo_storage
            db = mongo_storage._get_db()
            if db is not None:
                key_doc = db.api_keys.find_one({"key_hash": key_hash, "is_active": 1})
                if key_doc:
                    try:
                        db.api_keys.update_one({"id": key_doc["id"]}, {"$set": {"last_used_at": now_iso}})
                    except Exception:
                        pass
                    return {
                        "key_id": key_doc["id"],
                        "user_id": key_doc["user_id"],
                        "tier": key_doc.get("tier", "developer"),
                        "label": key_doc["label"],
                    }
        except Exception as e:
            logger.warning(f"Mongo validate_api_key failed ({e}), falling back to SQLite.")

    conn = sqlite3.connect(storage.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, user_id, tier, label FROM api_keys WHERE key_hash = ? AND is_active = 1",
            (key_hash,),
        ).fetchone()
        if row:
            conn.execute("UPDATE api_keys SET last_used_at = ? WHERE id = ?", (now_iso, row["id"]))
            conn.commit()
            return dict(row)
    finally:
        conn.close()

    return None
