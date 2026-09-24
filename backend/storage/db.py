from typing import Generator, Tuple
import time
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from core.config import settings

# Engine configuration with URL normalization for Supabase PostgreSQL
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif db_url.startswith("postgresql://") and "+psycopg2" not in db_url:
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

is_sqlite = db_url.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}
pool_kwargs = {} if is_sqlite else {
    "pool_size": 10,
    "max_overflow": 20,
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    **pool_kwargs,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> Tuple[bool, str]:
    """Test database connectivity and return status and latency."""
    start_time = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        latency_ms = (time.perf_counter() - start_time) * 1000
        return True, f"Connected ({latency_ms:.1f}ms)"
    except Exception as e:
        return False, f"Connection failed: {str(e)}"
