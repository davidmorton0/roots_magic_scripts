"""Print the structure of a RootsMagic .rmtree (SQLite) database.

Opens the file read-only. Lists every table with its columns, indexes
and row count, plus views and triggers.

With no TABLE arguments the full report is written to
tmp/output/general/<timestamp>_schema.txt; with TABLE arguments it is printed.

Usage: python schema.py PATH_TO_RMTREE [TABLE ...]
"""

import sqlite3
import sys
from contextlib import nullcontext
from pathlib import Path

from rmutils import connect_readonly, db_path_arg, output_file, quote


def print_table(conn: sqlite3.Connection, table: str) -> None:
    count = conn.execute(f"SELECT COUNT(*) FROM {quote(table)}").fetchone()[0]
    print(f"\n== {table}  ({count} rows)")

    for _, name, ctype, notnull, default, pk in conn.execute(
        f"PRAGMA table_info({quote(table)})"
    ):
        flags = []
        if pk:
            flags.append(f"PK{pk if pk > 1 else ''}")
        if notnull:
            flags.append("NOT NULL")
        if default is not None:
            flags.append(f"DEFAULT {default}")
        print(f"   {name:<28} {ctype or '-':<12} {' '.join(flags)}")

    for _, idx_name, unique, origin, _ in conn.execute(
        f"PRAGMA index_list({quote(table)})"
    ):
        cols = []
        for _, _, col, _, coll, key in conn.execute(
            f"PRAGMA index_xinfo({quote(idx_name)})"
        ):
            if key:
                cols.append(f"{col} COLLATE {coll}" if coll != "BINARY" else col)
        kind = "UNIQUE INDEX" if unique else "INDEX"
        print(f"   {kind} {idx_name} ({', '.join(cols)})  [{origin}]")


def report(conn: sqlite3.Connection, path: Path, wanted: list[str]) -> None:
    print(f"File: {path}")
    print(f"SQLite library: {sqlite3.sqlite_version}")
    print(f"user_version: {conn.execute('PRAGMA user_version').fetchone()[0]}")

    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
    ]
    if wanted:
        lower = {t.lower(): t for t in tables}
        missing = [w for w in wanted if w.lower() not in lower]
        if missing:
            print(f"Tables not found: {', '.join(missing)}")
        tables = [lower[w.lower()] for w in wanted if w.lower() in lower]
    else:
        print(f"Tables: {len(tables)}")

    for table in tables:
        print_table(conn, table)

    if not wanted:
        for kind in ("view", "trigger"):
            rows = conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type=? ORDER BY name",
                (kind,),
            ).fetchall()
            print(f"\n== {kind}s: {len(rows)}")
            for name, sql in rows:
                print(f"   {name}\n{sql}\n")


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2

    wanted = sys.argv[2:]
    conn = connect_readonly(path)
    try:
        with nullcontext() if wanted else output_file("schema"):
            report(conn, path, wanted)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
