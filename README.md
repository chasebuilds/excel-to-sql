# excel-to-sql

[![ci](https://github.com/chasebuilds/excel-to-sql/actions/workflows/ci.yml/badge.svg)](https://github.com/chasebuilds/excel-to-sql/actions/workflows/ci.yml) ![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue) [![MIT license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Loads a CSV or Excel sheet into a SQL table. It reads the values to pick each column's type (yes/no, whole number, money, decimal number, date, date and time, text), cleans the column names to `snake_case`, marks which columns can be empty, suggests a primary key, and prints a load report: rows loaded, rows rejected and why. SQLite by default; any SQLAlchemy database URL (Postgres, MySQL) works too.

## Measured result

Generated columns with a known type were run through the type check, and a generated 100,000 row table was loaded into SQLite. The table below is written by the benchmark script from a real run, not typed by hand. Method and per-type results: [BENCHMARK.md](BENCHMARK.md).

<!-- benchmark:start -->
| Measure | Result |
|---|---:|
| Generated columns with a known type | 2,000 |
| Type inferred right | **100.0%** (2,000 of 2,000) |
| Rows loaded into SQLite (8 columns, inference included) | 100,000 |
| Load speed | **4,363 rows/sec** (22.92 s) |
| Planted bad rows rejected | 500 of 500 |
<!-- benchmark:end -->

The test columns are generated and each one uses a single written style, so real exports with mixed styles will score lower. [LIMITATIONS.md](LIMITATIONS.md) lists the cases it gets wrong.

## Quick start

Windows (on macOS or Linux use `.venv/bin/` in place of `.venv\Scripts\`):

```
python -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\x2sql schema samples\customers.csv
.venv\Scripts\x2sql load samples\customers.csv --db x2sql-out\out.db --table customers --key customer_id
```

The sample is 60 generated customers with a planted bad money value, a duplicate ID and one blank signup date. `schema` prints:

```
CREATE TABLE "customers" (
    "customer_id" BIGINT NOT NULL,
    "full_name" TEXT NOT NULL,
    "zip_code" TEXT NOT NULL,
    "balance" NUMERIC(18, 2) NOT NULL,
    "signup_date" DATE,
    "last_order_at" TIMESTAMP,
    "is_active" BOOLEAN NOT NULL,
    "score" DOUBLE PRECISION NOT NULL,
    PRIMARY KEY ("zip_code")
);
```

`customer_id` has a planted duplicate, so the suggested key is `zip_code`, the first unique column with no blanks. Passing `--key customer_id` uses that column and rejects the duplicate. `load` prints:

```
60 rows read, 58 loaded, 2 rejected into customers (replace, key: customer_id)
  1 x bad decimal
  1 x duplicate key
  row 12: bad decimal: balance = 'about $40'
  row 22: duplicate key: customer_id = 1020
```

| Option | Effect |
|---|---|
| `--db PATH_OR_URL` | SQLite file (made if missing) or a SQLAlchemy URL such as `postgresql://user@host/db` |
| `--table NAME` | table name (default: the file name in `snake_case`) |
| `--key COLUMN` | primary key column, by its cleaned name (default: the suggested key) |
| `--mode replace` | drop and recreate the table (default) |
| `--mode append` | insert into the table, creating it if missing |
| `--mode upsert` | needs `--key`; rows whose key is already in the table are replaced, new keys are added |
| `--sheet NAME` | sheet to read from an Excel file (default: the first) |

Exit codes: `0` done (even with rejected rows), `2` the file, key, mode or database could not be used.

## How types are picked

A column gets the first type in this list that at least 98% of its non-blank values fit. Values that do not fit reject their row, with the reason in the report.

| Type | Accepts | SQL type |
|---|---|---|
| bool | `yes/no`, `true/false`, `y/n`, `t/f` (any case) | `BOOLEAN` |
| int | `42`, `-7`, `1,234` | `BIGINT` |
| decimal (money) | `$1,234.50`, `-$4.00`, `12.30` (needs a `$` or exactly two decimals) | `NUMERIC(18, 2)` |
| float | `3.14159`, `1e3` | `DOUBLE PRECISION` |
| date | `2024-01-31`, `01/31/2024`, `1/31/24`, `Jan 31 2024` | `DATE` |
| datetime | `2024-01-31 10:00:00`, `2024-01-31T10:00` | `TIMESTAMP` |
| text | anything else, and numbers with a leading zero (`02134`) | `TEXT` |

Blank, `null`, `none`, `n/a`, `na`, `nan` and `-` count as empty. A column with any empty value is nullable. Excel cells that are already numbers, dates or booleans are used as they are.

Reasons a row is rejected: `bad <type>` (a value does not fit the column type), `missing value` (empty in a NOT NULL or key column), `duplicate key` (the key repeats in the file; the first one is kept), `too many values` (a CSV row longer than the header).

As a library:

```python
from excel_to_sql.read import read_table
from excel_to_sql.load import load

header, rows = read_table("data.xlsx")
report = load(header, rows, "out.db", "customers", mode="upsert", key="customer_id")
report.loaded, report.rejects[:3]
```

## Limits

Short version: it reads one sheet per run, picks types by rules (no guessing from column names), and money values typed as plain Excel numbers load as floats. Full list: [LIMITATIONS.md](LIMITATIONS.md).

## Development

```
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest --cov
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m mypy
.venv\Scripts\python -m benchmark.run_benchmark
```

The sample file was made with `python -m benchmark.generate --seed 7 --rows 60 --out samples/customers.csv`. Tests use SQLite only.

## License

MIT. See [LICENSE](LICENSE).
