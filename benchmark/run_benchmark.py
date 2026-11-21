"""Score type inference, time a load, write BENCHMARK.md and the README table."""

from __future__ import annotations

import argparse
import platform
import re
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from benchmark.generate import columns, customers
from excel_to_sql.infer import infer_type
from excel_to_sql.load import load

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Score:
    cols: int
    right: int
    by_type: dict[str, tuple[int, int]]
    misses: Counter[tuple[str, str]]
    load_rows: int
    loaded: int
    rejected: int
    seconds: float


def score(seed: int, n_cols: int, col_len: int, load_rows: int) -> Score:
    cols = columns(seed, n_cols, col_len)
    by: dict[str, list[int]] = {}
    misses: Counter[tuple[str, str]] = Counter()
    for truth, values in cols:
        got = infer_type(values)
        hit = by.setdefault(truth, [0, 0])
        hit[1] += 1
        if got == truth:
            hit[0] += 1
        else:
            misses[(truth, got)] += 1
    header, rows = customers(seed, load_rows)
    for i in range(0, load_rows, 200):
        rows[i][3] = "about $40"
    with tempfile.TemporaryDirectory() as d:
        start = time.perf_counter()
        r = load(header, rows, str(Path(d) / "b.db"), "customers", key="customer_id")
        seconds = time.perf_counter() - start
    return Score(
        cols=n_cols,
        right=sum(v[0] for v in by.values()),
        by_type={k: (v[0], v[1]) for k, v in sorted(by.items())},
        misses=misses,
        load_rows=load_rows,
        loaded=r.loaded,
        rejected=len(r.rejects),
        seconds=seconds,
    )


def table(s: Score) -> str:
    rate = s.load_rows / s.seconds
    return "\n".join([
        "| Measure | Result |",
        "|---|---:|",
        f"| Generated columns with a known type | {s.cols:,} |",
        f"| Type inferred right | **{100 * s.right / s.cols:.1f}%** ({s.right:,} of {s.cols:,}) |",
        f"| Rows loaded into SQLite (8 columns, inference included) | {s.load_rows:,} |",
        f"| Load speed | **{rate:,.0f} rows/sec** ({s.seconds:.2f} s) |",
        f"| Planted bad rows rejected | {s.rejected:,} of {s.load_rows // 200:,} |",
    ])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--cols", type=int, default=2000)
    ap.add_argument("--col-len", type=int, default=200)
    ap.add_argument("--rows", type=int, default=100_000)
    a = ap.parse_args()
    s = score(a.seed, a.cols, a.col_len, a.rows)
    t = table(s)
    per_type = "\n".join(
        f"| {k} | {h:,} of {n:,} | {100 * h / n:.1f}% |" for k, (h, n) in s.by_type.items()
    )
    miss = "\n".join(f"| {a_} | {b} | {n} |" for (a_, b), n in s.misses.most_common()) or "| none | | |"
    md = f"""# Benchmark

Written by `python -m benchmark.run_benchmark --seed {a.seed} --cols {a.cols} --col-len {a.col_len} --rows {a.rows}`. Numbers come from that run, not typed by hand.

Machine: {platform.system()} {platform.release()}, Python {platform.python_version()}.

{t}

## Method

- **Type inference:** {a.cols:,} synthetic columns of {a.col_len} values each. Each column gets a true type (bool, int, decimal money, float, date, datetime, text) and one written style for that type (for example `$1,234.56` or `12.30` for money, ISO or US dates, zip codes with a leading zero for text). About 10% of values are blank. The inferred type is compared to the true type.
- **Load speed:** a generated customers table of {a.rows:,} rows and 8 columns is read from memory, typed, checked and written to a new SQLite file with `customer_id` as the key. Every 200th row has a bad money value (`about $40`), so the report should reject exactly those. Time covers inference, conversion and insert, not reading the file from disk.

## Per type

| True type | Right | Rate |
|---|---:|---:|
{per_type}

## Misses (true type, inferred type, count)

| True | Inferred | Columns |
|---|---|---:|
{miss}

These are generated columns, so they are cleaner than real exports. See [LIMITATIONS.md](LIMITATIONS.md).
"""
    (ROOT / "BENCHMARK.md").write_text(md, encoding="utf-8")
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    text = re.sub(r"<!-- benchmark:start -->.*<!-- benchmark:end -->",
                  f"<!-- benchmark:start -->\n{t}\n<!-- benchmark:end -->", text, flags=re.S)
    readme.write_text(text, encoding="utf-8")
    print(t)


if __name__ == "__main__":
    main()
