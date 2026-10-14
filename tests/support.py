"""Shared test setup: import path, a small fixture database, a frozen clock."""

import io
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import rmutils  # noqa: E402

FIXED_NOW = datetime(2026, 1, 2, 3, 4, 5)
FIXED_STAMP = "20260102_030405"

PEOPLE = [
    # PersonID, Sex
    (1, 0),
    (2, 1),
    (3, 0),
    (4, 1),
]
NAMES = [
    # OwnerID, Surname, Given, Prefix, Suffix, IsPrimary, BirthYear, DeathYear
    (1, "smith", "John", None, None, 1, 1850, 1910),
    (2, "Brown", "Mary", "Dr", None, 1, 1860, 0),
    (3, "Brown", "Albert", None, "Jr", 1, 0, 0),
    (3, "Brownley", "Bert", None, None, 0, 0, 0),  # alternate name, not listed
    # PersonID 4 has no primary name
]


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FIXED_NOW


def build_db(path: Path) -> None:
    """Create a minimal .rmtree-like database with an RMNOCASE index."""
    conn = sqlite3.connect(path)
    conn.create_collation("RMNOCASE", rmutils.rmnocase)
    conn.executescript(
        """
        CREATE TABLE PersonTable (PersonID INTEGER PRIMARY KEY, Sex INTEGER);
        CREATE TABLE NameTable (
            NameID INTEGER PRIMARY KEY, OwnerID INTEGER,
            Surname TEXT, Given TEXT, Prefix TEXT, Suffix TEXT,
            IsPrimary INTEGER, BirthYear INTEGER, DeathYear INTEGER);
        CREATE INDEX idxSurname ON NameTable (Surname COLLATE RMNOCASE);
        """
    )
    conn.executemany("INSERT INTO PersonTable VALUES (?, ?)", PEOPLE)
    conn.executemany(
        "INSERT INTO NameTable (OwnerID, Surname, Given, Prefix, Suffix,"
        " IsPrimary, BirthYear, DeathYear) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        NAMES,
    )
    conn.commit()
    conn.close()


class ScriptTestCase(unittest.TestCase):
    """Fixture database in a temp dir, output dir redirected, clock frozen."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.db = self.tmp / "test.rmtree"
        build_db(self.db)
        self.output_dir = self.tmp / "output"
        for target, value in (
            ("rmutils.OUTPUT_DIR", self.output_dir),
            ("rmutils.datetime", FixedDatetime),
        ):
            patcher = mock.patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_main(self, main, *args: str) -> tuple[int, str]:
        """Call a script's main() with argv set; return (exit code, stdout)."""
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["script", *args]), redirect_stdout(out):
            code = main()
        return code, out.getvalue()

    def output_path(self, name: str) -> Path:
        return self.output_dir / f"{FIXED_STAMP}_{name}.txt"
