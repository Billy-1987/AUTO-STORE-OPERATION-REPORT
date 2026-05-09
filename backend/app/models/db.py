# 文件作用：SQLAlchemy 引擎 + Session（连写库 Doris）
# 版本：v0.1.0

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

from app.config import get_settings


def _build_url() -> str:
    s = get_settings()
    return (
        f"mysql+pymysql://{s.doris_rw_user}:{s.doris_rw_password}"
        f"@{s.doris_rw_host}:{s.doris_rw_port}/{s.doris_rw_db}?charset=utf8mb4"
    )


_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(_build_url(), pool_pre_ping=True, pool_recycle=300, future=True)
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionLocal


def get_db() -> Session:
    """FastAPI Depends 用"""
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
