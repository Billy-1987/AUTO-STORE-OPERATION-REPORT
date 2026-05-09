# 文件作用：6 张元数据表的 SQLAlchemy ORM 映射
# 版本：v0.1.0
#
# Doris 注意：
# - 不支持 FK 约束，关系靠应用层
# - ARRAY/JSON 字段在这里映射为 String（写入时手工 json.dumps，读取时手工 json.loads）

from datetime import datetime
from sqlalchemy import (
    BigInteger, Integer, String, Text, DateTime, Date, SmallInteger, Numeric
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Prompt(Base):
    __tablename__ = "prompts"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    report_type: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[int] = mapped_column(SmallInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trigger_type: Mapped[str] = mapped_column(String(16))
    report_type: Mapped[str] = mapped_column(String(32))
    prompt_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    period_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    sql_dump: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_dump: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_rendered: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_estimate: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Recipient(Base):
    __tablename__ = "recipients"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column("role", String(32))   # role 是保留字
    region_ids: Mapped[str | None] = mapped_column(Text, nullable=True)  # ARRAY<INT> via JSON string
    shop_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    dingtalk_userid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dingtalk_mobile: Mapped[str | None] = mapped_column(String(32), nullable=True)
    subscribe_weekly: Mapped[int] = mapped_column(SmallInteger, default=1)
    subscribe_monthly: Mapped[int] = mapped_column(SmallInteger, default=1)
    subscribe_holiday: Mapped[int] = mapped_column(SmallInteger, default=1)
    is_active: Mapped[int] = mapped_column(SmallInteger, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Schedule(Base):
    __tablename__ = "schedules"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    report_type: Mapped[str] = mapped_column(String(32))
    cron_expression: Mapped[str] = mapped_column(String(64))
    is_active: Mapped[int] = mapped_column(SmallInteger, default=1)
    prompt_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recipient_filter: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_run_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(BigInteger)
    report_type: Mapped[str] = mapped_column(String(32))
    period_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scope: Mapped[str | None] = mapped_column(String(32), nullable=True)
    scope_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    html_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    public_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    dingtalk_status: Mapped[str] = mapped_column(String(16), default="pending")
    dingtalk_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Holiday(Base):
    __tablename__ = "holidays"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64))
    start_date: Mapped[datetime] = mapped_column(Date)
    end_date: Mapped[datetime] = mapped_column(Date)
    year: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[int] = mapped_column(SmallInteger, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
