import datetime as dt
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa

from excel_to_sql.cli import main
from excel_to_sql.infer import (
    clean_names,
    create_table_sql,
    infer_columns,
    infer_type,
    suggest_key,
    to_decimal,
)
from excel_to_sql.load import load


def test_clean_names() -> None:
    assert clean_names(["Customer ID", "OrderDate", "#Items", "2024 Sales", None, "a", "A"]) == [
        "customer_id", "order_date", "items", "c_2024_sales", "column_5", "a", "a_2",
    ]


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (["yes", "no", "Y", ""], "bool"),
        (["1", "-20", "1,234"], "int"),
        (["$1,200.00", "3.50", "-$4.00"], "decimal"),
        (["1.5", "2.25", "3"], "float"),
        (["2024-01-31", "12/25/2023"], "date"),
        (["2024-01-31 10:00:00", "2024-02-01T08:30"], "datetime"),
        (["02134", "10001"], "text"),
        (["abc", "1"], "text"),
        ([None, ""], "text"),
        ([True, 3], "text"),
        ([dt.datetime(2024, 1, 1), dt.datetime(2024, 1, 2)], "date"),
        ([dt.datetime(2024, 1, 1, 5), dt.date(2024, 1, 2)], "datetime"),
        ([1.0, 2.0], "int"),
    ],
)
def test_infer_type(values: list[object], expected: str) -> None:
    assert infer_type(values) == expected


def test_decimal_sign() -> None:
    assert to_decimal("-$4.00") == Decimal("-4.00")
    assert to_decimal("$-4") == Decimal("-4")


HEADER = ["Customer ID", "Name", "Balance", "Joined", "Active"]
ROWS = [
    ["1", "Ana", "$10.00", "2024-01-02", "yes"],
    ["2", "Bo", "$0.50", "", "no"],
    ["3", "Cy", "$7.25", "2024-03-04", "yes"],
]


def test_columns_and_key() -> None:
    cols = infer_columns(HEADER, ROWS)
    assert [(c.name, c.type, c.nullable) for c in cols] == [
        ("customer_id", "int", False),
        ("name", "text", False),
        ("balance", "decimal", False),
        ("joined", "date", True),
        ("active", "bool", False),
    ]
    assert suggest_key(cols) == "customer_id"
    sql = create_table_sql("customers", cols, "customer_id")
    assert '"customer_id" BIGINT NOT NULL' in sql
    assert 'PRIMARY KEY ("customer_id")' in sql


def _rows(db: Path, q: str) -> list[tuple[object, ...]]:
    e = sa.create_engine(f"sqlite:///{db}")
    with e.connect() as c:
        out = [tuple(r) for r in c.execute(sa.text(q))]
    e.dispose()
    return out


def test_load_rejects_and_modes(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    r = load(HEADER, ROWS, str(db), "customers")
    assert (r.read, r.loaded, len(r.rejects)) == (3, 3, 0)
    # many good rows so one bad value is under the 2% tolerance
    big = [[str(i), f"n{i}", "$1.00", "2024-01-01", "no"] for i in range(1, 101)]
    big.append(["oops", "z", "$1.00", "2024-01-01", "no"])
    big.append(["5", "dup", "$1.00", "2024-01-01", "no"])
    big.append(["200", "wide", "$1.00", "2024-01-01", "no", "extra"])
    r = load(HEADER, big, str(db), "customers", "replace", "customer_id")
    assert r.loaded == 100
    assert sorted(r.reasons()) == ["bad int", "duplicate key", "too many values"]
    assert "row 102" in r.summary()
    # upsert: change row 1, add row 501, reject 500 (joined is NOT NULL now)
    up = [
        ["1", "Ann", "$2.00", "2024-01-01", "yes"],
        ["500", "New", "$3.00", "", "no"],
        ["501", "N", "$3.00", "2024-05-05", "no"],
    ]
    r = load(HEADER, up, str(db), "customers", "upsert", "customer_id")
    assert (r.loaded, r.rejects[0].reason) == (2, "missing value: joined")
    assert _rows(db, "select count(*) from customers") == [(101,)]
    assert _rows(db, "select name, balance from customers where customer_id=1") == [("Ann", 2.0)]
    r = load(HEADER, [["600", "A", "$1.00", "2024-01-01", "no"]], str(db), "customers", "append")
    assert _rows(db, "select count(*) from customers") == [(102,)]


def test_load_errors(tmp_path: Path) -> None:
    db = str(tmp_path / "t.db")
    with pytest.raises(ValueError, match="upsert needs"):
        load(HEADER, ROWS, db, "t", "upsert")
    with pytest.raises(ValueError, match="mode"):
        load(HEADER, ROWS, db, "t", "merge")
    with pytest.raises(ValueError, match="not a column"):
        load(HEADER, ROWS, db, "t", "replace", "nope")
    load(["a"], [["1"]], db, "t")
    with pytest.raises(ValueError, match="no column"):
        load(["b"], [["1"]], db, "t", "append")
    r = load(["a", "b"], [["1", ""], ["", "2"]], db, "u")
    assert r.key is None and r.loaded == 2


def test_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from openpyxl import Workbook

    xl = tmp_path / "My Customers.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["ID", "Signup Date", "Score"])
    ws.append([1, dt.datetime(2024, 1, 5), 1.5])
    ws.append([2, dt.datetime(2024, 2, 5), 2.5])
    wb.save(xl)
    assert main(["schema", str(xl)]) == 0
    out = capsys.readouterr().out
    assert 'CREATE TABLE "my_customers"' in out and '"signup_date" DATE' in out
    db = tmp_path / "o.db"
    assert main(["load", str(xl), "--db", str(db), "--table", "c"]) == 0
    assert "2 loaded, 0 rejected" in capsys.readouterr().out
    csv = tmp_path / "d.csv"
    csv.write_text("a,b\n1,x\n", encoding="utf-8")
    assert main(["load", str(csv), "--db", f"sqlite:///{db}", "--mode", "append",
                 "--table", "d"]) == 0
    assert main(["schema", str(tmp_path / "missing.csv")]) == 2
    (tmp_path / "e.csv").write_text("", encoding="utf-8")
    assert main(["schema", str(tmp_path / "e.csv")]) == 2
