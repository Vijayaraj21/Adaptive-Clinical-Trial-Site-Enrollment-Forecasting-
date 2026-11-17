"""MySQL persistence for trial panels, protocol metadata, and user accounts."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import pymysql
import yaml
from dotenv import load_dotenv


class MySQLStore:
    def __init__(self, settings: dict[str, Any], password: str):
        self.host = str(settings.get("host", "127.0.0.1"))
        self.port = int(settings.get("port", 3306))
        self.username = str(settings.get("username", "root"))
        self.database = str(settings.get("name", "mygem"))
        if not re.fullmatch(r"[A-Za-z0-9_]+", self.database):
            raise ValueError("MySQL database name may contain only letters, numbers, and underscores.")
        self.password = password
        try:
            self._ensure_database()
            self._ensure_schema()
        except pymysql.MySQLError as exc:
            raise RuntimeError(
                "Could not connect to MySQL. Start the local MySQL server and verify the configured account and password."
            ) from exc

    @classmethod
    def from_config_file(cls, config_path: str) -> MySQLStore | None:
        load_dotenv()
        with open(config_path, "r", encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file) or {}
        settings = config.get("database", {})
        if not settings.get("enabled", False):
            return None
        password_name = str(settings.get("password_env", "MYSQL_PASSWORD"))
        password = os.getenv(password_name)
        if not password:
            raise RuntimeError(f"Set {password_name} in .env to enable MySQL persistence.")
        return cls(settings, password)

    def _connect(self, database: bool = True) -> pymysql.Connection:
        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.username,
            password=self.password,
            database=self.database if database else None,
            charset="utf8mb4",
            autocommit=True,
            connect_timeout=5,
            cursorclass=pymysql.cursors.DictCursor,
        )

    def _ensure_database(self) -> None:
        with self._connect(database=False) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{self.database}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )

    def _ensure_schema(self) -> None:
        statements = [
            """CREATE TABLE IF NOT EXISTS weekly_site_panel (
                site_id VARCHAR(128) NOT NULL,
                week SMALLINT UNSIGNED NOT NULL,
                row_data JSON NOT NULL,
                PRIMARY KEY (site_id, week)
            ) ENGINE=InnoDB""",
            """CREATE TABLE IF NOT EXISTS trial_metadata (
                trial_id VARCHAR(64) NOT NULL PRIMARY KEY,
                metadata JSON NOT NULL
            ) ENGINE=InnoDB""",
            """CREATE TABLE IF NOT EXISTS app_users (
                username VARCHAR(128) NOT NULL PRIMARY KEY,
                full_name VARCHAR(255) NOT NULL,
                role VARCHAR(32) NOT NULL,
                email VARCHAR(255) NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT NOT NULL,
                permissions JSON NOT NULL,
                password_salt CHAR(32) NOT NULL,
                password_hash CHAR(64) NOT NULL
            ) ENGINE=InnoDB""",
            """CREATE TABLE IF NOT EXISTS auth_sessions (
                token_hash CHAR(64) NOT NULL PRIMARY KEY,
                username VARCHAR(128) NOT NULL,
                expires_at DATETIME NOT NULL,
                INDEX idx_auth_sessions_username (username),
                CONSTRAINT fk_auth_sessions_user FOREIGN KEY (username)
                    REFERENCES app_users(username) ON DELETE CASCADE
            ) ENGINE=InnoDB""",
        ]
        with self._connect() as connection:
            with connection.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)

    def load_panel(self, seed_panel: pd.DataFrame) -> pd.DataFrame:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT row_data FROM weekly_site_panel ORDER BY site_id, week")
                rows = cursor.fetchall()
        if not rows:
            self.save_panel(seed_panel)
            return seed_panel.copy()
        records = [row["row_data"] for row in rows]
        records = [json.loads(row) if isinstance(row, str) else row for row in records]
        return pd.DataFrame.from_records(records)

    def save_panel(self, panel: pd.DataFrame) -> None:
        if panel.empty:
            return
        records = json.loads(panel.to_json(orient="records"))
        values = [
            (str(row["site_id"]), int(row["week"]), json.dumps(row, separators=(",", ":")))
            for row in records
        ]
        statement = """INSERT INTO weekly_site_panel (site_id, week, row_data)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE row_data = VALUES(row_data)"""
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(statement, values)

    def load_metadata(self, trial_id: str, fallback: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT metadata FROM trial_metadata WHERE trial_id = %s", (trial_id,))
                row = cursor.fetchone()
        if row:
            metadata = row["metadata"]
            return json.loads(metadata) if isinstance(metadata, str) else metadata
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO trial_metadata (trial_id, metadata) VALUES (%s, %s) "
                    "ON DUPLICATE KEY UPDATE metadata = VALUES(metadata)",
                    (trial_id, json.dumps(fallback, separators=(",", ":"))),
                )
        return fallback

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 310_000).hex()

    def seed_users(self, users: dict[str, dict[str, Any]]) -> None:
        statement = """INSERT IGNORE INTO app_users
            (username, full_name, role, email, title, description, permissions, password_salt, password_hash)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        values = []
        for username, user in users.items():
            salt = secrets.token_hex(16)
            values.append((
                username,
                user["full_name"],
                user["role"],
                user["email"],
                user["title"],
                user["description"],
                json.dumps(user["permissions"]),
                salt,
                self._hash_password(user["password"], salt),
            ))
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(statement, values)

    def register_user(self, username: str, full_name: str, email: str, password: str) -> dict[str, Any] | None:
        normalized_username = username.lower()
        salt = secrets.token_hex(16)
        permissions = ["view_kpi", "view_forecast", "view_sites"]
        statement = """INSERT INTO app_users
            (username, full_name, role, email, title, description, permissions, password_salt, password_hash)
            VALUES (%s, %s, 'user', %s, 'Trial Observer', 'Read-only dashboard access', %s, %s, %s)"""
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        statement,
                        (
                            normalized_username,
                            full_name.strip(),
                            email.lower(),
                            json.dumps(permissions),
                            salt,
                            self._hash_password(password, salt),
                        ),
                    )
        except pymysql.err.IntegrityError:
            return None
        return {
            "username": normalized_username,
            "full_name": full_name.strip(),
            "role": "user",
            "email": email.lower(),
            "permissions": permissions,
        }

    @staticmethod
    def _user_from_row(row: dict[str, Any]) -> dict[str, Any]:
        permissions = row["permissions"]
        return {
            "username": row["username"],
            "full_name": row["full_name"],
            "role": row["role"],
            "email": row["email"],
            "title": row["title"],
            "description": row["description"],
            "permissions": json.loads(permissions) if isinstance(permissions, str) else permissions,
        }

    def authenticate_user(self, username: str, password: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM app_users WHERE username = %s", (username.lower(),))
                row = cursor.fetchone()
        if not row:
            return None
        expected = self._hash_password(password, row["password_salt"])
        if not hmac.compare_digest(expected, row["password_hash"]):
            return None
        return self._user_from_row(row)

    def issue_token(self, username: str) -> str:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=7)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO auth_sessions (token_hash, username, expires_at) VALUES (%s, %s, %s)",
                    (token_hash, username.lower(), expires_at),
                )
        return token

    def change_password(self, username: str, old_password: str, new_password: str) -> str:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT password_salt, password_hash FROM app_users WHERE username = %s", (username,))
                row = cursor.fetchone()
                if not row:
                    return "not_found"
                expected = self._hash_password(old_password, row["password_salt"])
                if not hmac.compare_digest(expected, row["password_hash"]):
                    return "incorrect_password"
                salt = secrets.token_hex(16)
                cursor.execute(
                    "UPDATE app_users SET password_salt = %s, password_hash = %s WHERE username = %s",
                    (salt, self._hash_password(new_password, salt), username),
                )
        return "success"

    def get_user_for_token(self, token: str) -> dict[str, Any] | None:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT users.* FROM auth_sessions AS sessions "
                    "JOIN app_users AS users ON users.username = sessions.username "
                    "WHERE sessions.token_hash = %s AND sessions.expires_at > UTC_TIMESTAMP()",
                    (token_hash,),
                )
                row = cursor.fetchone()
        return self._user_from_row(row) if row else None