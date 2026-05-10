# 文件作用：把中国法定节假日（国务院公告）一次性写入 holidays 表
# 版本：v0.1.0 — 2025 / 2026 两年，按 (name, year) 幂等
#
# 用法：
#   cd backend && source .venv/bin/activate && python scripts/seed_holidays.py
#
# 数据来源：
#   2025：国务院 2024-11-12 公告
#   2026：国务院 2025-11-13 公告（春节、劳动节、国庆节延长后的版本）
#
# ⚠️ TODO 2027：国务院通常在 2026-11 月公告下一年节假日安排。
#    届时往下方 HOLIDAYS 列表追加 2027 年的 7 条记录（元旦 / 春节 / 清明 / 劳动 / 端午 / 中秋 / 国庆），
#    然后重跑本脚本即可（已有记录会跳过，只插入新增）。
#
# 注意 holidays.id 在 ORM 里用 _gen_id() 客户端生成，避开 Doris AUTO_INCREMENT。

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

# 让脚本独立可跑：把 backend/ 加进 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.db import get_session_factory
from app.models.entities import Holiday


HOLIDAYS: list[tuple[str, int, date, date]] = [
    # 2025
    ("元旦",   2025, date(2025, 1, 1),  date(2025, 1, 1)),
    ("春节",   2025, date(2025, 1, 28), date(2025, 2, 4)),
    ("清明节", 2025, date(2025, 4, 4),  date(2025, 4, 6)),
    ("劳动节", 2025, date(2025, 5, 1),  date(2025, 5, 5)),
    ("端午节", 2025, date(2025, 5, 31), date(2025, 6, 2)),
    ("国庆中秋", 2025, date(2025, 10, 1), date(2025, 10, 8)),

    # 2026
    ("元旦",   2026, date(2026, 1, 1),  date(2026, 1, 3)),
    ("春节",   2026, date(2026, 2, 15), date(2026, 2, 23)),
    ("清明节", 2026, date(2026, 4, 4),  date(2026, 4, 6)),
    ("劳动节", 2026, date(2026, 5, 1),  date(2026, 5, 5)),
    ("端午节", 2026, date(2026, 6, 19), date(2026, 6, 21)),
    ("中秋节", 2026, date(2026, 9, 25), date(2026, 9, 27)),
    ("国庆节", 2026, date(2026, 10, 1), date(2026, 10, 8)),
]


def main() -> int:
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        existing = {
            (h.name, h.year): h
            for h in db.query(Holiday).all()
        }

        inserted = 0
        skipped = 0
        for name, year, start, end in HOLIDAYS:
            if (name, year) in existing:
                skipped += 1
                continue
            db.add(Holiday(
                name=name, year=year,
                start_date=start, end_date=end,
                is_active=1,
            ))
            inserted += 1
        db.commit()
        print(f"inserted={inserted} skipped={skipped} total_in_table={db.query(Holiday).count()}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
