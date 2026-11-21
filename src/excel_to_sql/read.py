"""Read a CSV or Excel sheet into a header and rows."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def read_table(path: str | Path, sheet: str | None = None) -> tuple[list[Any], list[list[Any]]]:
    p = Path(path)
    if p.suffix.lower() in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook

        wb = load_workbook(p, read_only=True, data_only=True)
        ws = wb[sheet] if sheet else wb.worksheets[0]
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        wb.close()
    else:
        with p.open(newline="", encoding="utf-8-sig") as f:
            rows = [list(r) for r in csv.reader(f)]
    rows = [r for r in rows if any(v not in (None, "") for v in r)]
    if not rows:
        raise ValueError(f"{p} has no rows")
    return rows[0], rows[1:]
