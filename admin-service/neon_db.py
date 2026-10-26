"""PostgreSQL persistence for paid gift cards (Neon).

The current interview administration remains on SQLite until migrated separately.
No secrets are logged. Schema installation is deliberate, never on import.
"""
import os
from pathlib import Path


def connection():
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL is not configured.")
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("Install psycopg[binary] in the Render build command.") from exc
    return psycopg.connect(url, connect_timeout=10)


def check_connection():
    """Read-only health probe; avoids printing the secret URL."""
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone()[0] == 1


def initialize_schema():
    """Apply idempotent DDL explicitly during controlled setup."""
    schema = Path(__file__).with_name("neon_schema.sql").read_text(encoding="utf-8")
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(schema)
