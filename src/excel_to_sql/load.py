"""Load rows into a SQL table and report what was loaded and rejected."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import sqlalchemy as sa

from excel_to_sql.infer import CONVERTERS, Column, infer_columns, is_null, suggest_key

SA_TYPES: dict[str, Any] = {
    "bool": sa.Boolean(),
    "int": sa.BigInteger(),
    "decimal": sa.Numeric(18, 2, asdecimal=False),
    "float": sa.Float(),
    "date": sa.Date(),
    "datetime": sa.DateTime(),
    "text": sa.Text(),
}
MODES = ("replace", "append", "upsert")
BATCH = 1000


@dataclass
class Reject:
    row: int
    reason: str


@dataclass
class Report:
    table: str
    mode: str
    key: str | None
    read: int = 0
    loaded: int = 0
    rejects: list[Reject] = field(default_factory=list)

    def reasons(self) -> Counter[str]:
        return Counter(r.reason.split(":")[0] for r in self.rejects)

    def summary(self) -> str:
        lines = [
            f"{self.read} rows read, {self.loaded} loaded, {len(self.rejects)} rejected "
            f"into {self.table} ({self.mode}, key: {self.key or 'none'})"
        ]
        lines += [f"  {n} x {why}" for why, n in self.reasons().most_common()]
        lines += [f"  row {r.row}: {r.reason}" for r in self.rejects[:5]]
        return "\n".join(lines)


def convert_rows(
    cols: Sequence[Column], rows: Sequence[Sequence[Any]], key: str | None
) -> tuple[list[dict[str, Any]], list[Reject]]:
    """Convert raw rows to typed dicts. Row numbers match the spreadsheet (header is row 1)."""
    good: list[dict[str, Any]] = []
    rejects: list[Reject] = []
    seen: set[Any] = set()
    for n, raw in enumerate(rows, 2):
        if len(raw) > len(cols) and any(not is_null(v) for v in raw[len(cols):]):
            rejects.append(Reject(n, f"too many values: {len(raw)} for {len(cols)} columns"))
            continue
        rec: dict[str, Any] = {}
        reason = None
        for i, c in enumerate(cols):
            v = raw[i] if i < len(raw) else None
            if is_null(v):
                if not c.nullable or c.name == key:
                    reason = f"missing value: {c.name}"
                    break
                rec[c.name] = None
                continue
            try:
                rec[c.name] = CONVERTERS[c.type](v)
            except (ValueError, TypeError):
                reason = f"bad {c.type}: {c.name} = {str(v)[:40]!r}"
                break
        if reason is None and key is not None:
            if rec[key] in seen:
                reason = f"duplicate key: {key} = {rec[key]!r}"
            seen.add(rec[key])
        if reason:
            rejects.append(Reject(n, reason))
        else:
            good.append(rec)
    return good, rejects


def build_table(name: str, cols: Sequence[Column], key: str | None) -> sa.Table:
    return sa.Table(
        name,
        sa.MetaData(),
        *[
            sa.Column(c.name, SA_TYPES[c.type], primary_key=c.name == key, nullable=c.nullable)
            for c in cols
        ],
    )


def load(
    header: Sequence[Any],
    rows: Sequence[Sequence[Any]],
    db: str,
    table: str,
    mode: str = "replace",
    key: str | None = None,
) -> Report:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {', '.join(MODES)}")
    if mode == "upsert" and not key:
        raise ValueError("upsert needs --key")
    cols = infer_columns(header, rows)
    names = [c.name for c in cols]
    if key and key not in names:
        raise ValueError(f"key {key!r} is not a column (columns: {', '.join(names)})")
    key = key or suggest_key(cols)
    report = Report(table, mode, key, read=len(rows))
    if "://" not in db:
        Path(db).parent.mkdir(parents=True, exist_ok=True)
        db = f"sqlite:///{db}"
    engine = sa.create_engine(db)
    with engine.begin() as conn:
        exists = sa.inspect(conn).has_table(table)
        if mode == "replace" or not exists:
            t = build_table(table, cols, key)
            if exists:
                t.drop(conn)
            t.create(conn)
        else:
            t = sa.Table(table, sa.MetaData(), autoload_with=conn)
            missing = [n for n in names if n not in t.c]
            if missing:
                raise ValueError(f"table {table} has no column(s): {', '.join(missing)}")
            for c in cols:
                c.nullable = bool(t.c[c.name].nullable)
        good, report.rejects = convert_rows(cols, rows, key)
        for i in range(0, len(good), BATCH):
            batch = good[i : i + BATCH]
            if mode == "upsert" and key:
                conn.execute(t.delete().where(t.c[key].in_([r[key] for r in batch])))
            conn.execute(t.insert(), batch)
    engine.dispose()
    report.loaded = len(good)
    return report
