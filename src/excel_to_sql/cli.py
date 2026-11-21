"""Command line: x2sql load and x2sql schema."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa

from excel_to_sql.infer import create_table_sql, infer_columns, snake, suggest_key
from excel_to_sql.load import MODES, load
from excel_to_sql.read import read_table


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="x2sql", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("load", "schema"):
        p = sub.add_parser(name)
        p.add_argument("file")
        p.add_argument("--sheet")
        p.add_argument("--table", help="table name (default: the file name in snake_case)")
        p.add_argument("--key", help="primary key column (default: suggested)")
        if name == "load":
            p.add_argument("--db", required=True, help="SQLite file or SQLAlchemy URL")
            p.add_argument("--mode", choices=MODES, default="replace")
    a = ap.parse_args(argv)
    table = a.table or snake(Path(a.file).stem) or "data"
    try:
        header, rows = read_table(a.file, a.sheet)
        if a.cmd == "schema":
            cols = infer_columns(header, rows)
            key = a.key or suggest_key(cols)
            print(create_table_sql(table, cols, key))
            return 0
        report = load(header, rows, a.db, table, a.mode, a.key)
    except (OSError, ValueError, KeyError, sa.exc.SQLAlchemyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(report.summary())
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
