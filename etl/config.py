"""Database settings shared by every script and notebook.

The defaults match docker-compose.yml and the local set-up in README.md (database, user and password are all "foodsafety").
Override with environment variables, or put them in a file called .env in the project root (see .env.example):
    FS_DB_HOST  FS_DB_PORT  FS_DB_NAME  FS_DB_USER  FS_DB_PASSWORD
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_env = ROOT / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

DB = {
    "host": os.environ.get("FS_DB_HOST", "localhost"),
    "port": os.environ.get("FS_DB_PORT", "5432"),
    "dbname": os.environ.get("FS_DB_NAME", "foodsafety"),
    "user": os.environ.get("FS_DB_USER", "foodsafety"),
    "password": os.environ.get("FS_DB_PASSWORD", "foodsafety"),
}
DSN = " ".join(f"{k}={v}" for k, v in DB.items())


def connect(**overrides):
    """Open a psycopg2 connection to the project database."""
    import psycopg2
    return psycopg2.connect(**{**DB, **overrides})
