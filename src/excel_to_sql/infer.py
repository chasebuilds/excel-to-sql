"""Column name cleanup and type inference from cell values."""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

NULLS = {"", "null", "none", "n/a", "na", "nan", "-"}
TRUE = {"true", "yes", "y", "t"}
FALSE = {"false", "no", "n", "f"}
DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%b %d %Y", "%d %b %Y"]
DATETIME_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
]
INT_RE = re.compile(r"^[+-]?(0|[1-9]\d*|[1-9]\d{0,2}(,\d{3})+)$")
LEADING_ZERO_RE = re.compile(r"^[+-]?0\d")
MONEY_RE = re.compile(r"^(-?)\$?(-?)(\d{1,3}(,\d{3})+|\d+)(\.\d{2})?$")
SQL_TYPES = {
    "bool": "BOOLEAN",
    "int": "BIGINT",
    "decimal": "NUMERIC(18, 2)",
    "float": "DOUBLE PRECISION",
    "date": "DATE",
    "datetime": "TIMESTAMP",
    "text": "TEXT",
}
THRESHOLD = 0.98


def is_null(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip().lower() in NULLS)


def snake(name: str) -> str:
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(name).strip())
    s = re.sub(r"[^0-9a-zA-Z]+", "_", s).strip("_").lower()
    return f"c_{s}" if s[:1].isdigit() else s


def clean_names(names: Sequence[Any]) -> list[str]:
    out: list[str] = []
    for i, n in enumerate(names, 1):
        base = snake(n) if n is not None else ""
        base = base or f"column_{i}"
        name, k = base, 2
        while name in out:
            name, k = f"{base}_{k}", k + 1
        out.append(name)
    return out


def to_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in TRUE:
        return True
    if s in FALSE:
        return False
    raise ValueError("not a yes/no value")


def to_int(v: Any) -> int:
    if isinstance(v, bool):
        raise ValueError("bool")
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    s = str(v).strip()
    if not INT_RE.match(s):
        raise ValueError("not a whole number")
    return int(s.replace(",", ""))


def to_decimal(v: Any) -> Decimal:
    if not isinstance(v, str):
        raise ValueError("not text money")
    s = v.strip()
    m = MONEY_RE.match(s)
    if not m or not ("$" in s or m.group(5)):
        raise ValueError("not a money amount")
    try:
        d = Decimal(m.group(3).replace(",", "") + (m.group(5) or ""))
    except InvalidOperation as e:  # pragma: no cover
        raise ValueError("not a money amount") from e
    return -d if (m.group(1) or m.group(2)) else d


def to_float(v: Any) -> float:
    if isinstance(v, bool):
        raise ValueError("bool")
    if isinstance(v, int | float):
        return float(v)
    s = str(v).strip().replace(",", "")
    if LEADING_ZERO_RE.match(s):
        raise ValueError("leading zero, kept as text")
    f = float(s)
    if f != f or f in (float("inf"), float("-inf")):
        raise ValueError("not a finite number")
    return f


def _parse_time(v: Any, formats: list[str]) -> dt.datetime:
    s = str(v).strip()
    for fmt in formats:
        try:
            return dt.datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError("not a recognized date format")


def to_date(v: Any) -> dt.date:
    if isinstance(v, dt.datetime):
        if v.time() != dt.time():
            raise ValueError("has a time part")
        return v.date()
    if isinstance(v, dt.date):
        return v
    return _parse_time(v, DATE_FORMATS).date()


def to_datetime(v: Any) -> dt.datetime:
    if isinstance(v, dt.datetime):
        return v
    if isinstance(v, dt.date):
        return dt.datetime(v.year, v.month, v.day)
    return _parse_time(v, DATETIME_FORMATS + DATE_FORMATS)


def to_text(v: Any) -> str:
    return str(v).strip()


CONVERTERS: dict[str, Callable[[Any], Any]] = {
    "bool": to_bool,
    "int": to_int,
    "decimal": to_decimal,
    "float": to_float,
    "date": to_date,
    "datetime": to_datetime,
    "text": to_text,
}


@dataclass
class Column:
    source: str
    name: str
    type: str
    nullable: bool
    unique: bool


def infer_type(values: Sequence[Any]) -> str:
    vals = [v for v in values if not is_null(v)]
    if not vals:
        return "text"
    for t, conv in CONVERTERS.items():
        ok = 0
        for v in vals:
            try:
                conv(v)
                ok += 1
            except (ValueError, TypeError):
                pass
        if ok / len(vals) >= THRESHOLD:
            return t
    return "text"  # pragma: no cover


def infer_columns(header: Sequence[Any], rows: Sequence[Sequence[Any]]) -> list[Column]:
    cols: list[Column] = []
    for i, name in enumerate(clean_names(header)):
        values = [r[i] if i < len(r) else None for r in rows]
        t = infer_type(values)
        present = [CONVERTERS[t](v) for v in values if not is_null(v) and _converts(t, v)]
        cols.append(
            Column(
                source=str(header[i]) if header[i] is not None else "",
                name=name,
                type=t,
                nullable=any(is_null(v) for v in values),
                unique=len(present) == len(values) and len(set(present)) == len(present),
            )
        )
    return cols


def _converts(t: str, v: Any) -> bool:
    try:
        CONVERTERS[t](v)
        return True
    except (ValueError, TypeError):
        return False


def suggest_key(cols: Sequence[Column]) -> str | None:
    """Pick a unique non-null column, preferring names that look like ids."""
    cands = [c for c in cols if c.unique and c.type in ("int", "text")]
    for c in cands:
        if c.name == "id" or c.name.endswith("_id"):
            return c.name
    return cands[0].name if cands else None


def create_table_sql(table: str, cols: Sequence[Column], key: str | None) -> str:
    lines = []
    for c in cols:
        parts = [f'    "{c.name}" {SQL_TYPES[c.type]}']
        if not c.nullable or c.name == key:
            parts.append("NOT NULL")
        lines.append(" ".join(parts))
    if key:
        lines.append(f'    PRIMARY KEY ("{key}")')
    return f'CREATE TABLE "{table}" (\n' + ",\n".join(lines) + "\n);"
