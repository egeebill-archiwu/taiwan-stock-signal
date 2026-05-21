"""
台股布林通道交易訊號系統 - 資料庫設定

負責 SQLite 資料庫的初始化、Session 管理及資料表建立。
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator

from backend.config import DATABASE_URL
from backend.data.models import Base


# 建立資料庫引擎（SQLite 需要 check_same_thread=False 供多執行緒使用）
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
    pool_pre_ping=True,
)

# Session 工廠
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_all_tables() -> None:
    """
    建立所有資料表

    根據 models.py 中定義的 ORM 模型，在資料庫中建立對應的資料表。
    若資料表已存在則不會重複建立。
    """
    Base.metadata.create_all(bind=engine)


def drop_all_tables() -> None:
    """
    刪除所有資料表（僅用於測試或重置）
    """
    Base.metadata.drop_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI 依賴注入用的資料庫 Session 產生器

    使用方式：
        @app.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager 形式的資料庫 Session

    使用方式：
        with get_db_session() as db:
            db.query(...)
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
