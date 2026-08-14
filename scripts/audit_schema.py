#!/usr/bin/env python3
"""Audit model-vs-DB schema mismatches (created while completing OpenAgentNet)."""
from __future__ import annotations

import asyncio

import asyncpg

from app.models import Base
from app.models import *  # noqa: ensure models registered  # type: ignore

URL = "postgresql://openagentnet:openagentnet@localhost:5432/openagentnet"


async def main() -> None:
    conn = await asyncpg.connect(URL)
    rows = await conn.fetch(
        """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        """
    )
    db_cols: dict[str, set[str]] = {}
    for r in rows:
        db_cols.setdefault(r["table_name"], set()).add(r["column_name"])

    problems: list[tuple[str, str]] = []
    for table in sorted(db_cols):
        sa_table = Base.metadata.tables.get(table)
        if sa_table is None:
            problems.append((table, "no SA model"))
            continue
        model_cols = {c.name for c in sa_table.columns}
        for c in sorted(model_cols - db_cols[table]):
            problems.append((table, f"MODEL col {c} missing in DB"))
        for c in sorted(db_cols[table] - model_cols):
            problems.append((table, f"DB col {c} missing in MODEL"))
    if problems:
        for t, msg in problems:
            print(f"{t} -> {msg}")
    else:
        print("ALL MATCH")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
