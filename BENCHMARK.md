# Benchmark

Written by `python -m benchmark.run_benchmark --seed 7 --cols 2000 --col-len 200 --rows 100000`. Numbers come from that run, not typed by hand.

Machine: Windows 10, Python 3.11.15.

| Measure | Result |
|---|---:|
| Generated columns with a known type | 2,000 |
| Type inferred right | **100.0%** (2,000 of 2,000) |
| Rows loaded into SQLite (8 columns, inference included) | 100,000 |
| Load speed | **4,363 rows/sec** (22.92 s) |
| Planted bad rows rejected | 500 of 500 |

## Method

- **Type inference:** 2,000 synthetic columns of 200 values each. Each column gets a true type (bool, int, decimal money, float, date, datetime, text) and one written style for that type (for example `$1,234.56` or `12.30` for money, ISO or US dates, zip codes with a leading zero for text). About 10% of values are blank. The inferred type is compared to the true type.
- **Load speed:** a generated customers table of 100,000 rows and 8 columns is read from memory, typed, checked and written to a new SQLite file with `customer_id` as the key. Every 200th row has a bad money value (`about $40`), so the report should reject exactly those. Time covers inference, conversion and insert, not reading the file from disk.

## Per type

| True type | Right | Rate |
|---|---:|---:|
| bool | 319 of 319 | 100.0% |
| date | 278 of 278 | 100.0% |
| datetime | 280 of 280 | 100.0% |
| decimal | 273 of 273 | 100.0% |
| float | 298 of 298 | 100.0% |
| int | 274 of 274 | 100.0% |
| text | 278 of 278 | 100.0% |

## Misses (true type, inferred type, count)

| True | Inferred | Columns |
|---|---|---:|
| none | | |

These are generated columns, so they are cleaner than real exports. See [LIMITATIONS.md](LIMITATIONS.md).
