"""Neon connection validation and optional gift table initialization.

Usage:
  python admin-service/check_neon.py
  python admin-service/check_neon.py --init
Do not print secrets or the connection string.
"""
import sys
from neon_db import check_connection, initialize_schema


if __name__ == "__main__":
    if "--init" in sys.argv:
        initialize_schema()
        print("Neon gift tables initialized.")
    if not check_connection():
        raise SystemExit("Neon database did not return SELECT 1.")
    print("Neon connection verified.")
