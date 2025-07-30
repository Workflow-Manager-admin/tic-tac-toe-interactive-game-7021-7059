"""
Database configuration and SQLAlchemy setup for FastAPI app.

PUBLIC_INTERFACE:
    Provides get_db() dependency for FastAPI routes.
    Exposes Base (for Alembic migrations) and engine/session management.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.declarative import declarative_base
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tic_tac_toe.db")

# Example: use NullPool for SQLite dev, can switch to default for Postgres, etc.
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=NullPool
    )
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# PUBLIC_INTERFACE
def get_db():
    """
    Yields a SQLAlchemy session for dependency injection in FastAPI endpoints.
    Example:
        db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
