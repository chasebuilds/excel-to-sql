window.DEMO = {
  repo: "excel-to-sql",
  title: "excel-to-sql",
  tagline: "Drop in a CSV or Excel sheet. Get a typed CREATE TABLE, a suggested key, and the rows loaded into a SQLite database, with every row that would not fit (bad numbers, duplicate keys) rejected and listed.",
  pkg: "excel_to_sql",
  packages: ["openpyxl", "sqlalchemy", "sqlite3"],
  inputs: [
    { id: "input", label: "CSV or XLSX", accept: ".csv,.xlsx,.xlsm", sample: "samples/customers.csv" },
  ],
  options: [
    { id: "table", label: "Table name", type: "text", value: "", placeholder: "from the file name" },
    { id: "key", label: "Primary key column", type: "text", value: "customer_id", placeholder: "suggested" },
  ],
  sampleNote: 'The sample is <a href="samples/customers.csv">customers.csv</a>: 60 synthetic customers with a planted bad money value, a duplicate ID and one blank signup date. For your own file, clear the key box to use the suggested key.<br>SQLite and SQLAlchemy both have official Pyodide builds; the database is written in the page and offered as a download.',
  python: `
import sqlite3
from pathlib import Path
from excel_to_sql.cli import main as cli_main
from excel_to_sql.infer import snake

def run(paths, opts):
    src = paths["input"][0]
    table = opts.get("table", "").strip() or snake(Path(src).stem) or "data"
    db = "/work/" + table + ".db"
    common = [src, "--table", table]
    if opts.get("key", "").strip():
        common += ["--key", opts["key"].strip()]
    code1, schema = run_cli(cli_main, ["schema", *common])
    code2, load = run_cli(cli_main, ["load", *common, "--db", db, "--mode", "replace"])
    log = schema.rstrip() + "\\n\\n" + load
    if code1 != 0 or code2 != 0 or not Path(db).exists():
        return {"ok": False, "log": log, "sheets": [], "download": None}
    con = sqlite3.connect(db)
    sheets = []
    for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"):
        cur = con.execute(f'SELECT * FROM "{name}" LIMIT 201')
        body = [["" if v is None else str(v) for v in r] for r in cur.fetchall()]
        total = con.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
        sheets.append({"name": name, "rows": [[d[0] for d in cur.description]] + body, "fills": None, "total": total})
    con.close()
    return {"ok": True, "log": log, "sheets": sheets, "download": db}
`,
};
