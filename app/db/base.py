from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config.env import (
    SQLALCHEMY_DATABASE_URL,
    SQLALCHEMY_CONNECTION_POOL_SIZE,
    SQLALCHEMY_CONNECTION_MAX_OVERFLOW,
)

IS_SQLITE = SQLALCHEMY_DATABASE_URL.startswith("sqlite")

if IS_SQLITE:
    # SQLite specific configuration to prevent connection pool freezing and leaks
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={
            "check_same_thread": False,
            "timeout": 30,  # 30 second timeout for busy database
        },
        poolclass=StaticPool,  # Use StaticPool to prevent connection leaks
        pool_pre_ping=True,  # Verify connections before using them
        # echo=True
    )

    # Enable WAL mode for better concurrency
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")  # 30 seconds
        cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
        cursor.close()
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
