import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Local Postgres is provided by docker compose; the default matches it.
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg2://app:app@db:5432/appdb"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
