"""Shared fixture for the validate_*.py tests: invented records, each new check failing a known number
of times."""

from pathlib import Path

from rmutils import sort_date
from support import ScriptTestCase

EXAMPLE_CONFIG = Path(__file__).resolve().parent.parent / "config.example.toml"
ROOT = "H:\\My Drive\\Records"
NO_SORT = 9223372036854775807


def sd(date: str) -> int:
    return sort_date(date)


EXTRA_SQL = f"""
DROP TABLE FactTypeTable;
CREATE TABLE FactTypeTable (FactTypeID INTEGER PRIMARY KEY, OwnerType INTEGER, Name TEXT, UseDate INTEGER,
    UsePlace INTEGER);
CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, Name TEXT);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER, CitationName TEXT);
CREATE TABLE MultimediaTable (MediaID INTEGER PRIMARY KEY, MediaType INTEGER, MediaPath TEXT, MediaFile TEXT,
    Date TEXT, SortDate BIGINT);

INSERT INTO FactTypeTable VALUES (1, 0, 'Birth', 1, 1), (2, 0, 'Death', 1, 1), (3, 0, 'Christen', 1, 1),
    (300, 1, 'Marriage', 1, 1), (1006, 0, 'Census England 1881', 1, 1);
INSERT INTO PersonTable (PersonID, Sex, ParentID, SpouseID) VALUES
    (1, 0, 0, 1), (2, 1, 0, 1), (3, 0, 1, 0), (4, 2, 9, 1), (5, 0, 0, 0);
INSERT INTO NameTable (NameID, OwnerID, Given, Surname, Prefix, Suffix, Nickname, IsPrimary, Date) VALUES
    (1, 1, 'John', 'Smith', '', '', '', 1, '.'),
    (2, 2, 'Mary', 'Smith', '', '', '', 1, '.'),
    (3, 3, 'Tom', 'Smith', '', '', '', 1, '.'),
    (4, 4, 'ann', 'BROWN', '', '', '', 1, '.'),
    (5, 1, ' John', 'Smith', '', '', '', 0, '.'),
    (6, 3, '', 'Smith', '', '', '', 0, '.'),
    (7, 99, 'Ghost', 'Name', '', '', '', 0, 'D.+18501301..+00000000..');
INSERT INTO FamilyTable (FamilyID, FatherID, MotherID) VALUES (1, 1, 2), (2, 1, 98), (3, 0, 2);
INSERT INTO ChildTable (RecID, ChildID, FamilyID) VALUES (1, 3, 1), (2, 97, 1), (3, 97, 1), (4, 3, 50);
INSERT INTO PlaceTable (PlaceID, PlaceType, Name, MasterID) VALUES
    (1, 0, 'Testham, Exampleshire, England', 0), (2, 2, 'St John', 1), (3, 2, 'St Johns', 1),
    (4, 1, 'TESTX - Test Temple', 0);
INSERT INTO FANTable VALUES (1, 0, 0);
INSERT INTO EventTable (EventID, EventType, OwnerType, OwnerID, PlaceID, SiteID, Date, SortDate, IsPrimary) VALUES
    (1, 1, 0, 1, 1, 2, 'D.+18500101..+00000000..', {sd('D.+18500101..+00000000..')}, 1),
    (2, 2, 0, 1, 1, 0, 'D.+19100000..+00000000..', {sd('D.+19100000..+00000000..')}, 1),
    (3, 1, 0, 2, 1, 0, 'D.+18600000..+00000000..', {sd('D.+18600000..+00000000..')}, 1),
    (4, 1, 0, 3, 1, 0, 'D.+18700000..+00000000..', {sd('D.+18700000..+00000000..')}, 1),
    (5, 300, 1, 1, 1, 0, 'D.+18650000..+00000000..', {sd('D.+18650000..+00000000..')}, 1),
    (6, 1, 0, 96, 1, 0, '.', {NO_SORT}, 1),
    (8, 1006, 0, 1, 1, 0, 'D.+18810403..+00000000..', 5, 1),
    (9, 1006, 0, 2, 1, 0, 'T1881 census', {NO_SORT}, 1);
INSERT INTO WitnessTable VALUES (1, 5, 95, 0, 39), (2, 999, 1, 0, 39);
INSERT INTO SourceTable VALUES (1, 'Census'), (2, 'Unused');
INSERT INTO CitationTable VALUES (1, 1, 'RG11'), (2, 1, 'RG12');
INSERT INTO CitationLinkTable (LinkID, CitationID, OwnerType, OwnerID, Quality) VALUES
    (1, 1, 2, 1, 'PIX'), (2, 1, 7, 50, '~~~'), (3, 2, 2, 2, 'PD'), (4, 9, 2, 1, 'PIX');
INSERT INTO MultimediaTable VALUES
    (1, 1, '{ROOT}\\Census', 'a.jpg', 'T19/02/2019 22:42:21', {NO_SORT}),
    (2, 1, '{ROOT}\\Census', 'b.pdf', 'D.+18810403..+00000000..', 0);
INSERT INTO MediaLinkTable (LinkID, MediaID, OwnerType, OwnerID) VALUES (1, 1, 4, 1);
INSERT INTO TaskTable (TaskID, Name, Date1, Date2, Date3) VALUES (1, 'Find birth', '.', '.', '.'),
    (2, 'Orphan task', 'D.+2020', '.', '.');
INSERT INTO TaskLinkTable (LinkID, TaskID, OwnerType, OwnerID) VALUES (1, 1, 0, 1), (2, 7, 0, 1), (3, 1, 0, 94),
    (4, 1, 3, 1);
"""

SCAN_FILES = [f"{ROOT}\\Census\\a.jpg", f"{ROOT}\\Census\\new.jpg"]


def summary_counts(out: str) -> dict[str, str]:
    """Code -> count (or "skipped") from a validate or check summary."""
    counts = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and (parts[0].isdigit() or parts[0] == "skipped") and "_" in parts[1]:
            counts[parts[1]] = parts[0]
    return counts


class ValidateTestCase(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.use_full_schema(EXTRA_SQL)
        self.scan_list = self.tmp / "scans.txt"
        self.scan_list.write_text("\n".join(SCAN_FILES), encoding="utf-8")

    def run_validate(self, main, *options: str) -> tuple[int, str]:
        return self.run_main(main, str(self.db), "--config", str(EXAMPLE_CONFIG), *options)
