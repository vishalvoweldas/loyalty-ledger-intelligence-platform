"""Database connection, session management, and transaction isolation."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.engine import Engine
import sqlite3
from typing import Generator
from loyalty_ledger.config import DATABASE_URL

Base = declarative_base()

import os

def _sqlite_on_connect(dbapi_con, con_record):
    if isinstance(dbapi_con, sqlite3.Connection):
        cursor = dbapi_con.cursor()
        cursor.execute("PRAGMA busy_timeout = 30000;")
        if os.environ.get("LOYALTY_DISABLE_FK") == "1":
            cursor.execute("PRAGMA foreign_keys=OFF;")
            cursor.execute("PRAGMA synchronous=OFF;")
            cursor.execute("PRAGMA cache_size=100000;")
        else:
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.close()

import re
from pathlib import Path

LFS_VERSION_LINE = b"version https://git-lfs.github.com/spec/v1"
LFS_OID_PATTERN = re.compile(rb"^oid sha256:[0-9a-fA-F]{64}$")
LFS_SIZE_PATTERN = re.compile(rb"^size \d+$")

def is_lfs_pointer(file_path: Path) -> bool:
    """Returns True ONLY if file_path exists, is a regular file, is < 1024 bytes,
    and strictly conforms to the official Git LFS pointer specification:
    1. First non-empty line is exactly 'version https://git-lfs.github.com/spec/v1'
    2. Contains a valid 'oid sha256:<64-hex-digits>' line
    3. Contains a valid 'size <integer>' line
    Guaranteed to return False for legitimate SQLite databases, arbitrary text
    files containing 'git-lfs', and malformed pointer-like files.
    """
    if not (file_path.exists() and file_path.is_file()):
        return False
    try:
        size = file_path.stat().st_size
        if size == 0 or size > 1024:
            return False
        with open(file_path, "rb") as f:
            content = f.read()

        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not lines or lines[0] != LFS_VERSION_LINE:
            return False

        has_oid = any(LFS_OID_PATTERN.match(line) for line in lines[1:])
        has_size = any(LFS_SIZE_PATTERN.match(line) for line in lines[1:])

        return bool(has_oid and has_size)
    except OSError:
        return False

def check_sqlite_lfs_pointer(db_url: str = DATABASE_URL) -> None:
    """Guards against treating an unresolved Git LFS pointer text file as a SQLite database.
    Raises RuntimeError on ordinary database access if the database file is an LFS pointer.
    """
    if db_url.startswith("sqlite:///"):
        path_str = db_url.replace("sqlite:///", "")
        if path_str and path_str != ":memory:":
            db_file = Path(path_str)
            if is_lfs_pointer(db_file):
                raise RuntimeError(
                    f"Database file '{db_file}' is an unresolved Git LFS pointer text file. "
                    f"To initialize a fresh local database, run: "
                    f"'python -m loyalty_ledger.cli generate --scale starter --seed 20261022'"
                )

def remove_lfs_pointer_if_present(db_url: str = DATABASE_URL) -> bool:
    """Removes an unresolved Git LFS pointer text file if present at db_url.
    Returns True if a pointer was removed, False otherwise.
    Guaranteed to NEVER delete a real SQLite database or any non-pointer file.
    """
    if db_url.startswith("sqlite:///"):
        path_str = db_url.replace("sqlite:///", "")
        if path_str and path_str != ":memory:":
            db_file = Path(path_str)
            if is_lfs_pointer(db_file):
                db_file.unlink()
                return True
    return False

def create_app_engine(db_url: str = DATABASE_URL) -> Engine:
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        connect_args["timeout"] = 30.0

    engine = create_engine(
        db_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        echo=False
    )

    if db_url.startswith("sqlite"):
        def _on_sqlite_connect(dbapi_con, con_record):
            # Guard against treating an unresolved Git LFS pointer as a SQLite database
            check_sqlite_lfs_pointer(db_url)
            _sqlite_on_connect(dbapi_con, con_record)

        event.listen(engine, "connect", _on_sqlite_connect)

        def _do_begin(conn):
            if conn.get_execution_options().get("sqlite_immediate", False):
                conn.exec_driver_sql("BEGIN IMMEDIATE")

        event.listen(engine, "begin", _do_begin)

    return engine

engine = create_app_engine()
SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def begin_write_transaction(session: Session) -> None:
    """Begins an immediate write transaction on SQLite to serialize concurrent writes.
    Prevents lock-upgrade deadlocks and race conditions on check-then-act operations
    (such as point redemptions, lot allocations, order returns, and expirations).
    Safe no-op on non-SQLite engines (e.g., PostgreSQL, which uses SELECT ... FOR UPDATE).
    """
    bind = session.get_bind()
    if bind.dialect.name == "sqlite":
        if not session.in_transaction():
            session.connection(execution_options={"sqlite_immediate": True})
        else:
            conn = session.connection()
            if not conn.get_execution_options().get("sqlite_immediate", False):
                # If only a deferred read lock was active with no pending writes,
                # rollback the read snapshot to acquire an immediate write lock without committing partial writes.
                if not (session.dirty or session.new or session.deleted):
                    session.rollback()
                    session.connection(execution_options={"sqlite_immediate": True})

def get_db() -> Generator[Session, None, None]:
    """FastAPI database session dependency with automatic transaction control."""
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def init_db(target_engine: Engine = engine):
    """Initializes tables in the target database."""
    Base.metadata.create_all(bind=target_engine)
