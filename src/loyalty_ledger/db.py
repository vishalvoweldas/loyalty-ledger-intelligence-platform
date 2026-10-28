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
        event.listen(engine, "connect", _sqlite_on_connect)

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
