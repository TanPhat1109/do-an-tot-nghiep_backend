from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

import config

engine = create_engine(
    config.DATABASE_URL,
    pool_pre_ping=True,   # tránh lỗi "MySQL server has gone away"
    pool_recycle=3600,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()