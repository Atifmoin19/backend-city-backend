"""In-memory SQLite databases for the Data Vaults games (shared with the browser).

Game starter code (never the learner's snippet) opens the vault with its seed data; the
learner only queries it. The guard blocks ATTACH (SQL that opens files on disk) and the
sandbox policy forbids the methods that would remove it.
"""

import sqlite3

_BLOCKED = (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH)


def _guard(action: int, *_: object) -> int:
    return sqlite3.SQLITE_DENY if action in _BLOCKED else sqlite3.SQLITE_OK


def open_vault(seed_sql: str) -> sqlite3.Connection:
    """A fresh in-memory database with `seed_sql` run in it (tables + rows)."""
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.executescript(seed_sql)  # trusted seed data, before the guard goes on
    db.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)
    db.set_authorizer(_guard)
    return db
