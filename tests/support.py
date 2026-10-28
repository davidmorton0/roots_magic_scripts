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

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
# rmutils.py sits in scripts/; the scripts themselves sit in its subfolders.
for folder in [SCRIPTS, *sorted(p for p in SCRIPTS.iterdir() if p.is_dir() and p.name != "__pycache__")]:
    sys.path.insert(0, str(folder))

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


FULL_SCHEMA = """
DROP TABLE IF EXISTS PersonTable;
DROP TABLE IF EXISTS NameTable;
CREATE TABLE PersonTable (PersonID INTEGER PRIMARY KEY, UniqueID TEXT, Sex INTEGER, ParentID INTEGER,
    SpouseID INTEGER, Color INTEGER, Color1 INTEGER, Color2 INTEGER, Color3 INTEGER, Color4 INTEGER, Color5 INTEGER,
    Color6 INTEGER, Color7 INTEGER, Color8 INTEGER, Color9 INTEGER, Relate1 INTEGER, Relate2 INTEGER, Flags INTEGER,
    Living INTEGER, IsPrivate INTEGER, Proof INTEGER, Bookmark INTEGER, Note TEXT, UTCModDate FLOAT);
CREATE TABLE NameTable (NameID INTEGER PRIMARY KEY, OwnerID INTEGER, Surname TEXT COLLATE RMNOCASE,
    Given TEXT COLLATE RMNOCASE, Prefix TEXT COLLATE RMNOCASE, Suffix TEXT COLLATE RMNOCASE,
    Nickname TEXT COLLATE RMNOCASE, NameType INTEGER, Date TEXT, SortDate BIGINT, IsPrimary INTEGER,
    IsPrivate INTEGER, Proof INTEGER, Sentence TEXT, Note TEXT, BirthYear INTEGER, DeathYear INTEGER,
    Display INTEGER, Language TEXT, UTCModDate FLOAT, SurnameMP TEXT, GivenMP TEXT, NicknameMP TEXT);
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, EventType INTEGER, OwnerType INTEGER, OwnerID INTEGER,
    FamilyID INTEGER, PlaceID INTEGER, SiteID INTEGER, Date TEXT, SortDate BIGINT, IsPrimary INTEGER,
    IsPrivate INTEGER, Proof INTEGER, Status INTEGER, Sentence TEXT, Details TEXT, Note TEXT, UTCModDate FLOAT);
CREATE TABLE FamilyTable (FamilyID INTEGER PRIMARY KEY, FatherID INTEGER, MotherID INTEGER, ChildID INTEGER,
    HusbOrder INTEGER, WifeOrder INTEGER, IsPrivate INTEGER, Proof INTEGER, SpouseLabel INTEGER, FatherLabel INTEGER,
    MotherLabel INTEGER, SpouseLabelStr TEXT, FatherLabelStr TEXT, MotherLabelStr TEXT, Note TEXT, UTCModDate FLOAT);
CREATE TABLE ChildTable (RecID INTEGER PRIMARY KEY, ChildID INTEGER, FamilyID INTEGER, RelFather INTEGER,
    RelMother INTEGER, ChildOrder INTEGER, IsPrivate INTEGER, ProofFather INTEGER, ProofMother INTEGER, Note TEXT,
    UTCModDate FLOAT);
CREATE TABLE PlaceTable (PlaceID INTEGER PRIMARY KEY, PlaceType INTEGER, Name TEXT COLLATE RMNOCASE, Abbrev TEXT,
    Normalized TEXT, Latitude INTEGER, Longitude INTEGER, LatLongExact INTEGER, MasterID INTEGER, Note TEXT,
    Reverse TEXT COLLATE RMNOCASE, fsID INTEGER, anID INTEGER, UTCModDate FLOAT);
CREATE TABLE FANTable (FANID INTEGER PRIMARY KEY, PlaceID INTEGER, SiteID INTEGER);
CREATE TABLE TaskTable (TaskID INTEGER PRIMARY KEY, TaskType INTEGER, RefNumber TEXT, Name TEXT COLLATE RMNOCASE,
    Status INTEGER, Priority INTEGER, Date1 TEXT, Date2 TEXT, Date3 TEXT, SortDate1 BIGINT, SortDate2 BIGINT,
    SortDate3 BIGINT, Filename TEXT, Details TEXT, Results TEXT, UTCModDate FLOAT, Exclude INTEGER);
CREATE TABLE TaskLinkTable (LinkID INTEGER PRIMARY KEY, TaskID INTEGER, OwnerType INTEGER, OwnerID INTEGER,
    UTCModDate FLOAT);
CREATE TABLE WitnessTable (WitnessID INTEGER PRIMARY KEY, EventID INTEGER, PersonID INTEGER, WitnessOrder INTEGER,
    Role INTEGER);
CREATE TABLE FactTypeTable (FactTypeID INTEGER PRIMARY KEY, OwnerType INTEGER, Name TEXT);
CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER, OwnerType INTEGER, OwnerID INTEGER,
    SortOrder INTEGER, Quality TEXT, IsPrivate INTEGER, Flags INTEGER, UTCModDate FLOAT);
CREATE TABLE MediaLinkTable (LinkID INTEGER PRIMARY KEY, MediaID INTEGER, OwnerType INTEGER, OwnerID INTEGER);
CREATE TABLE URLTable (LinkID INTEGER PRIMARY KEY, OwnerType INTEGER, OwnerID INTEGER);
CREATE TABLE AddressLinkTable (LinkID INTEGER PRIMARY KEY, OwnerType INTEGER, AddressID INTEGER, OwnerID INTEGER);
"""


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

    def use_full_schema(self, extra_sql: str = "") -> None:
        """Replace the small fixture tables with real-column tables (FULL_SCHEMA), then run extra_sql."""
        conn = sqlite3.connect(self.db)
        conn.create_collation("RMNOCASE", rmutils.rmnocase)
        conn.executescript(FULL_SCHEMA + extra_sql)
        conn.commit()
        conn.close()

    def query(self, sql: str) -> list[tuple]:
        conn = sqlite3.connect(self.db)
        conn.create_collation("RMNOCASE", rmutils.rmnocase)
        try:
            return conn.execute(sql).fetchall()
        finally:
            conn.close()

    def run_main(self, main, *args: str) -> tuple[int, str]:
        """Call a script's main() with argv set; return (exit code, stdout)."""
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["script", *args]), redirect_stdout(out):
            code = main()
        return code, out.getvalue()

    def output_path(self, name: str, folder: str = "general") -> Path:
        return self.output_dir / folder / f"{FIXED_STAMP}_{name}.txt"
