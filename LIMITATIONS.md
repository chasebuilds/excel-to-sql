# Limitations

What excel-to-sql does not do, or does poorly. Read this before trusting a loaded table.

## Type inference

- **Types come from values only.** A column named `zip` full of 5-digit numbers without a leading zero becomes `BIGINT`. Pass the data through a text step first, or fix the table by hand.
- **Money needs a `$` or exactly two decimals in text.** Excel cells formatted as currency arrive as plain numbers and load as `DOUBLE PRECISION`. Other currency symbols (`EUR`, the euro and pound signs) are text.
- **Dates are US or ISO.** `31/01/2024` (day first) is not read as a date. `01/02/2024` is always January 2. Time zones are not read.
- **The 98% rule can reject real data.** In a column of 1,000 numbers with 15 typos, the 15 rows are rejected, not loaded as text. With more than 2% bad values the whole column falls back to text.
- **The benchmark is generated data.** Each test column uses one written style, so the 100% score there is an upper bound, not what a messy export will get.

## Loading

- **One sheet per run.** Use `--sheet` and run again for each sheet.
- **Append and upsert use the table that is there.** Column types come from the file, not the table; a file column the table lacks stops the load. NOT NULL rules come from the table.
- **Upsert deletes then inserts in batches of 1,000**, in one transaction. It works on any database SQLAlchemy supports but is slower than a native `ON CONFLICT` on large tables.
- **Duplicate keys keep the first row.** Later rows with the same key are rejected, not merged.
- **No foreign keys, indexes or column renames** beyond the primary key.
- **Speed is modest.** About 4,000 rows a second on SQLite, because every value is parsed in Python. Large files (millions of rows) will be slow.
- **Postgres and other databases are not tested in CI.** Tests run on SQLite only.
