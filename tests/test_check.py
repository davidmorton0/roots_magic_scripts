import sqlite3
import unittest
from pathlib import Path
from unittest import mock

from support import ScriptTestCase

import check

EXAMPLE_CONFIG = Path(__file__).resolve().parent.parent / "config.example.toml"
ROOT = "H:\\My Drive\\Records"

EXTRA_TABLES = """
CREATE TABLE FactTypeTable (FactTypeID INTEGER PRIMARY KEY, Name TEXT,
    UseDate INTEGER, UsePlace INTEGER);
CREATE TABLE FamilyTable (FamilyID INTEGER PRIMARY KEY, FatherID INTEGER, MotherID INTEGER);
CREATE TABLE ChildTable (RecID INTEGER PRIMARY KEY, ChildID INTEGER, FamilyID INTEGER);
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, EventType INTEGER,
    OwnerType INTEGER, OwnerID INTEGER, PlaceID INTEGER, Date TEXT, IsPrimary INTEGER);
CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, Name TEXT);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER,
    CitationName TEXT);
CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER,
    OwnerType INTEGER, OwnerID INTEGER);
CREATE TABLE MultimediaTable (MediaID INTEGER PRIMARY KEY, MediaType INTEGER,
    MediaPath TEXT, MediaFile TEXT);
CREATE TABLE MediaLinkTable (LinkID INTEGER PRIMARY KEY, MediaID INTEGER,
    OwnerType INTEGER, OwnerID INTEGER);

INSERT INTO FactTypeTable VALUES
    (1, 'Birth', 1, 1), (2, 'Death', 1, 1), (3, 'Christen', 1, 1),
    (300, 'Marriage', 1, 1),
    (1006, 'Census England 1881', 1, 1), (1009, 'Census England 1911', 1, 1);
INSERT INTO FamilyTable VALUES (1, 1, 2);
INSERT INTO ChildTable (ChildID, FamilyID) VALUES (3, 1);
INSERT INTO EventTable VALUES
    (1, 1, 0, 1, 1, 'D.+18500101..+00000000..', 1),
    (2, 2, 0, 1, 1, 'D.+19100000..+00000000..', 1),
    (3, 1, 0, 2, 0, 'D.+18600000..+00000000..', 1),
    (4, 1, 0, 3, 1, 'D.+18550000..+00000000..', 1),
    (5, 1006, 0, 1, 1, 'D.+18910405..+00000000..', 1),
    (6, 1009, 0, 1, 1, 'D.+19110402..+00000000..', 1),
    (7, 300, 1, 1, 1, '.', 1);
INSERT INTO SourceTable VALUES (1, 'Census'), (2, 'Unused source');
INSERT INTO CitationTable VALUES (1, 1, 'RG11'), (2, 1, 'RG14'), (3, 1, 'Spare');
INSERT INTO CitationLinkTable (CitationID, OwnerType, OwnerID) VALUES
    (1, 2, 5), (2, 2, 6), (1, 2, 99);
INSERT INTO MultimediaTable VALUES
    (1, 1, 'H:\\My Drive\\Records\\Census', 'a.jpg'),
    (2, 1, 'H:\\My Drive\\Records\\Census', 'b.pdf'),
    (3, 1, 'planner', 'c.jpg'),
    (4, 1, 'H:\\My Drive\\Records\\Census', 'a.jpg');
INSERT INTO MediaLinkTable (MediaID, OwnerType, OwnerID) VALUES
    (1, 4, 1), (2, 2, 1), (4, 4, 1);
"""

SCAN_FILES = [
    f"{ROOT}\\Census\\a.jpg",
    f"{ROOT}\\Census\\new.jpg",
    f"{ROOT}\\Census\\unsure\\x.jpg",
    f"{ROOT}\\Unsorted\\y.jpg",
    f"{ROOT}\\File Naming.docx",
    f"{ROOT}\\Census\\notes.txt",
]

EXPECTED_COUNTS = {
    "scan_not_in_db": "1",
    "media_file_missing": "1",
    "media_outside_root": "1",
    "media_unlinked": "1",
    "media_not_on_citation": "1",
    "media_type_mismatch": "1",
    "media_duplicate": "1",
    "media_link_orphan": "0",
    "citation_no_media": "2",
    "citation_unused": "1",
    "citation_link_orphan": "1",
    "source_unused": "1",
    "record_event_no_citation": "0",
    "event_no_citation": "5",
    "event_no_date": "1",
    "event_no_place": "1",
    "fact_year_mismatch": "1",
    "date_style_unusual": "0",
    "event_before_birth": "0",
    "event_after_death": "1",
    "person_no_name": "1",
    "person_sex_code": "0",
    "person_no_events": "1",
    "person_no_birth": "1",
    "person_unconnected": "1",
    "person_multiple_primary": "0",
    "birth_after_death": "0",
    "family_one_partner": "0",
    "parent_age": "2",
    "family_event_age": "0",
}


def summary_counts(out: str) -> dict[str, str]:
    counts = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] in EXPECTED_COUNTS:
            counts[parts[1]] = parts[0]
    return counts


class CheckMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(EXTRA_TABLES)
        conn.close()
        self.scan_list = self.tmp / "scans.txt"
        self.scan_list.write_text("\n".join(SCAN_FILES), encoding="utf-8")

    def run_check(self, *options: str) -> tuple[int, str]:
        return self.run_main(
            check.main, str(self.db), "--config", str(EXAMPLE_CONFIG), *options
        )

    def test_summary_counts(self):
        code, out = self.run_check("--scan-list", str(self.scan_list))

        self.assertEqual(code, 0)
        self.assertTrue(out.startswith(f"Output written to: {self.output_path('check')}\n"))
        self.assertEqual(summary_counts(out), EXPECTED_COUNTS)

    def test_report_lists_records(self):
        self.run_check("--scan-list", str(self.scan_list))
        text = self.output_path("check").read_text(encoding="utf-8")

        expected = [
            "== scan_not_in_db: Scan files on disk not in the database (1)",
            f"   {ROOT}\\Census\\new.jpg",
            f"   {ROOT}\\Census\\b.pdf [M2]",
            "   planner\\c.jpg [M3]",
            f"   {ROOT}\\Census\\b.pdf [M2] -> Birth 1850-01-01 - John smith [P1] [E1]",
            f"   {ROOT}\\Census\\a.jpg [M1, M4]",
            "   Census: RG14 [C2] - Census England 1911 1911-04-02 - John smith [P1] [E6]",
            "   Census: Spare [C3] - (not used)",
            "   Census England 1881 1891-04-05 - John smith [P1] [E5]",
            "   Census England 1911 1911-04-02 - John smith [P1] [E6] - died 1910",
            "   Marriage (no date) - John smith & Dr Mary Brown [F1] [E7]",
            "   Albert Brown, Jr [P3] born 1855 - John smith [P1]: father aged 5",
            "   Albert Brown, Jr [P3] born 1855 - Dr Mary Brown [P2]: mother aged -5",
            "   (no primary name) [P4]",
        ]
        for line in expected:
            self.assertIn(line + "\n", text)

    def test_no_scans_skips_disk_checks(self):
        code, out = self.run_check("--no-scans")

        counts = summary_counts(out)
        self.assertEqual(code, 0)
        self.assertEqual(counts["scan_not_in_db"], "skipped")
        self.assertEqual(counts["media_file_missing"], "skipped")
        self.assertEqual(counts["media_unlinked"], "1")

    def test_lists_scans_through_windows_by_default(self):
        with mock.patch.object(check, "list_windows_files", return_value=SCAN_FILES) as lister:
            code, out = self.run_check()

        self.assertEqual(code, 0)
        lister.assert_called_once_with(ROOT)
        self.assertEqual(summary_counts(out), EXPECTED_COUNTS)

    def test_does_not_change_database(self):
        before = self.db.read_bytes()
        self.run_check("--scan-list", str(self.scan_list))
        self.assertEqual(self.db.read_bytes(), before)

    def test_missing_file(self):
        code, out = self.run_main(check.main, str(self.tmp / "nope.rmtree"))
        self.assertEqual(code, 2)
        self.assertIn("File not found", out)

    def test_no_arguments_prints_usage(self):
        code, out = self.run_main(check.main)
        self.assertEqual(code, 2)
        self.assertIn("Usage: python check.py", out)


if __name__ == "__main__":
    unittest.main()
