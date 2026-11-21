"""Seeded synthetic columns with a known true type, and a sample customers file."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import random
from collections.abc import Callable
from pathlib import Path

WORDS = ["alder", "birch", "cedar", "delta", "ember", "fjord", "grove", "harbor", "iris", "juniper"]
Gen = Callable[[random.Random], str]


def _day(r: random.Random) -> dt.date:
    return dt.date(2015, 1, 1) + dt.timedelta(days=r.randrange(4000))


def _moment(r: random.Random) -> dt.datetime:
    d = _day(r)
    return dt.datetime(d.year, d.month, d.day, r.randrange(24), r.randrange(60), r.randrange(60))


VARIANTS: dict[str, list[Gen]] = {
    "bool": [
        lambda r: r.choice(["yes", "no"]),
        lambda r: r.choice(["TRUE", "FALSE"]),
        lambda r: r.choice(["Y", "N"]),
    ],
    "int": [
        lambda r: str(r.randrange(-500, 100000)),
        lambda r: f"{r.randrange(1000, 9_000_000):,}",
    ],
    "decimal": [
        lambda r: f"${r.randrange(0, 500000) / 100:,.2f}",
        lambda r: f"{r.randrange(-50000, 500000) / 100:.2f}",
    ],
    "float": [
        lambda r: f"{r.uniform(-1000, 1000):.4f}",
        lambda r: f"{r.uniform(0, 1):.6f}",
    ],
    "date": [
        lambda r: _day(r).isoformat(),
        lambda r: _day(r).strftime("%m/%d/%Y"),
    ],
    "datetime": [
        lambda r: _moment(r).strftime("%Y-%m-%d %H:%M:%S"),
        lambda r: _moment(r).strftime("%Y-%m-%dT%H:%M"),
    ],
    "text": [
        lambda r: f"{r.choice(WORDS)} {r.choice(WORDS)}",
        lambda r: f"{r.randrange(0, 99999):05d}",
        lambda r: f"{r.choice('ABCDEFG')}{r.randrange(100, 999)}",
    ],
}


def columns(seed: int, n: int, length: int) -> list[tuple[str, list[str]]]:
    """n columns of `length` values each: (true type, values), about 10% blank."""
    r = random.Random(seed)
    out = []
    for _ in range(n):
        t = r.choice(list(VARIANTS))
        gen = r.choice(VARIANTS[t])
        out.append((t, ["" if r.random() < 0.1 else gen(r) for _ in range(length)]))
    return out


def customers(seed: int, n: int) -> tuple[list[str], list[list[str]]]:
    r = random.Random(seed)
    header = ["Customer ID", "Full Name", "Zip Code", "Balance", "Signup Date", "Last Order At",
              "Is Active", "Score"]
    rows = []
    for i in range(1, n + 1):
        rows.append([
            str(1000 + i),
            f"{r.choice(WORDS).title()} {r.choice(WORDS).title()}",
            f"{r.randrange(0, 99999):05d}",
            f"${r.randrange(0, 200000) / 100:,.2f}",
            _day(r).isoformat(),
            "" if r.random() < 0.2 else _moment(r).strftime("%Y-%m-%d %H:%M:%S"),
            r.choice(["yes", "no"]),
            f"{r.uniform(0, 100):.3f}",
        ])
    return header, rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--rows", type=int, default=60)
    ap.add_argument("--out", default="samples/customers.csv")
    a = ap.parse_args()
    header, rows = customers(a.seed, a.rows)
    rows[10][3] = "about $40"
    rows[20][0] = rows[19][0]
    rows[30][4] = ""
    with Path(a.out).open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([header, *rows])


if __name__ == "__main__":
    main()
