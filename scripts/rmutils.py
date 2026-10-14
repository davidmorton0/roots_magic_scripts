"""Shared helpers for RootsMagic .rmtree (SQLite) scripts."""

import sqlite3
import sys
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stdout
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "tmp" / "output"


def rmnocase(a: str, b: str) -> int:
    """Stand-in for RootsMagic's RMNOCASE collation: case-insensitive compare."""
    a, b = a.casefold(), b.casefold()
    return (a > b) - (a < b)


def connect_readonly(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    conn.create_collation("RMNOCASE", rmnocase)
    return conn


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def db_path_arg(doc: str) -> Path | None:
    """Return the .rmtree path from argv[1], or print usage/error and return None."""
    if len(sys.argv) < 2:
        print(doc)
        return None
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"File not found: {path}")
        return None
    return path


@contextmanager
def output_file(name: str) -> Iterator[Path]:
    """Send stdout to tmp/output/<YYYYMMDD_HHMMSS>_<name>.txt, then print its path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_{name}.txt"
    with path.open("w", encoding="utf-8") as f, redirect_stdout(f):
        yield path
    print(f"Output written to: {path}")
