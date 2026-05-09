# 文件作用：Doris 连接封装（MySQL 协议，pymysql 驱动）
# 提供只读库 (业务) 和写库 (项目自用) 两个连接工厂
# 版本：v0.1.0 — 初始化

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pandas as pd
import pymysql
from pymysql.cursors import DictCursor

from app.config import get_settings


def _connect(host: str, port: int, user: str, password: str, database: str) -> pymysql.Connection:
    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=True,
        connect_timeout=10,
        read_timeout=120,
    )


@contextmanager
def doris_ro():
    """业务只读库连接 (bigoffs_sync)"""
    s = get_settings()
    conn = _connect(s.doris_ro_host, s.doris_ro_port, s.doris_ro_user, s.doris_ro_password, s.doris_ro_db)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def doris_rw():
    """项目自用写库连接（待 bigoffs-db skill 初始化后可用）"""
    s = get_settings()
    if not s.doris_rw_host or not s.doris_rw_port:
        raise RuntimeError("Doris 写库未初始化，请先通过 bigoffs-db skill 开通")
    conn = _connect(s.doris_rw_host, s.doris_rw_port, s.doris_rw_user, s.doris_rw_password, s.doris_rw_db)
    try:
        yield conn
    finally:
        conn.close()


def query_ro(sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
    """只读库 → list[dict]"""
    with doris_ro() as conn, conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


def query_ro_df(sql: str, params: tuple | None = None) -> pd.DataFrame:
    """只读库 → pandas DataFrame"""
    return pd.DataFrame(query_ro(sql, params))


def execute_rw(sql: str, params: tuple | None = None) -> int:
    """写库 DDL/DML 执行，返回受影响行数"""
    with doris_rw() as conn, conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.rowcount
