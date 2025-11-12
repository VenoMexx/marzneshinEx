from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from sqlalchemy.pool import NullPool

from app.config.env import (
    SQLALCHEMY_DATABASE_URL,
    SQLALCHEMY_CONNECTION_POOL_SIZE,
    SQLALCHEMY_CONNECTION_MAX_OVERFLOW,
)

IS_SQLITE = SQLALCHEMY_DATABASE_URL.startswith("sqlite")

if IS_SQLITE:
    # SQLite specific configuration with NullPool to prevent connection leaks
    # NullPool creates a new connection for each checkout and closes it on return
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={
            "check_same_thread": False,
            "timeout": 30,  # 30 second timeout for busy database
        },
        poolclass=NullPool,  # No connection pooling - prevents leaks completely
        pool_pre_ping=False,  # Not needed with NullPool
        echo=False,
    )

    # Enable WAL mode for better concurrency
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")  # 30 seconds
        cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
        cursor.execute("PRAGMA temp_store=MEMORY")  # Keep temp tables in memory
        cursor.close()

    # Connection checkout event - ensure clean state
    @event.listens_for(engine, "checkout")
    def receive_checkout(dbapi_conn, connection_record, connection_proxy):
        """Ensure connection is in clean state on checkout"""
        cursor = dbapi_conn.cursor()
        # Rollback any pending transactions
        cursor.execute("ROLLBACK")
        cursor.close()

    # Connection close event - ensure proper disposal
    @event.listens_for(engine, "close")
    def receive_close(dbapi_conn, connection_record):
        """Ensure connection is properly closed and locks released"""
        try:
            cursor = dbapi_conn.cursor()
            # Rollback any uncommitted transactions before close
            cursor.execute("ROLLBACK")
            cursor.close()
        except Exception:
            pass
else:
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_size=SQLALCHEMY_CONNECTION_POOL_SIZE,
        max_overflow=SQLALCHEMY_CONNECTION_MAX_OVERFLOW,
        pool_recycle=3600,
        pool_timeout=10,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def dispose_engine():
    """
    Dispose of the engine's connection pool.
    This ensures all connections are closed and resources are freed.
    Should be called on application shutdown.
    """
    engine.dispose()
