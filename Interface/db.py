"""Database access for the Shona-Mandarin dictionary prototype.

One cached psycopg 3 connection is shared across Streamlit reruns. Every query
goes through `fetch()`, which reconnects once if the cached connection has been
dropped (Postgres restart, idle timeout).
"""

import os
from pathlib import Path

import psycopg
import streamlit as st
from dotenv import load_dotenv
from psycopg.rows import dict_row

APP_DIR = Path(__file__).resolve().parent
load_dotenv(APP_DIR / ".env")

MANDARIN_TABLE = "mandarin_entry_v2"
SHONA_TABLE = "shona_entry"

# Whitelist: the UI only ever selects a key from this map, so the column name
# interpolated into SQL can never come from user input.
EMBEDDING_COLUMNS = {
    "3a": "embedding_3a",
    "3b": "embedding_3b",
}

MANDARIN_DISPLAY_COLUMNS = [
    "simplified",
    "traditional",
    "pinyin",
    "english_gloss",
    "shiyi",
    "audio_url",
]

SHONA_DISPLAY_COLUMNS = [
    "headword",
    "english_gloss",
    "shona_definition",
    "shona_status",
]


def connection_settings():
    return {
        "host": os.getenv("PGHOST", "localhost"),
        "port": int(os.getenv("PGPORT", "5432")),
        "dbname": os.getenv("PGDATABASE", "mandarin_shona_database"),
        "user": os.getenv("PGUSER", "postgres"),
        "password": os.getenv("PGPASSWORD", "1244"),
    }


@st.cache_resource(show_spinner=False)
def get_connection():
    return psycopg.connect(**connection_settings(), row_factory=dict_row, autocommit=True)


def fetch(query, params=None):
    """Run a read query and return a list of dict rows."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()
    except psycopg.OperationalError:
        # Cached connection went stale — drop it and try once more.
        get_connection.clear()
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


def check_connection():
    """Return (ok, message) so the UI can report a clear failure at startup."""
    settings = connection_settings()
    try:
        fetch("SELECT 1 AS ok")
    except Exception as exc:  # noqa: BLE001 — surfaced to the user verbatim
        return False, f"{type(exc).__name__}: {exc}"

    missing = []
    for table in (MANDARIN_TABLE, SHONA_TABLE):
        rows = fetch("SELECT to_regclass(%s) AS found", (f"public.{table}",))
        if rows[0]["found"] is None:
            missing.append(table)
    if missing:
        return False, (
            f"Connected to {settings['dbname']}, but these tables are missing: "
            + ", ".join(missing)
        )
    return True, f"{settings['dbname']} on {settings['host']}:{settings['port']}"
