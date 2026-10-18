import sqlite3
import unittest
from datetime import date
from unittest import mock

from support import ScriptTestCase

import freebmd_death_citation
from rmutils import read_fields

SCAN = "H:\\My Drive\\Records\\Deaths\\Britain\\Registers\\SMI-J-DRB-1910-Q2.jpg"
TEXT = "Deaths Jun 1910\\nSMITH \\tJohn. \\t60 \\tMedway \\t 2a \\t383"


class FreeBmdDeathCitationMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript("""
            CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, TemplateID INTEGER);
            CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, EventType INTEGER,
                OwnerType INTEGER, OwnerID INTEGER);
            CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER,
                Comments TEXT, ActualText TEXT, RefNumber TEXT, Footnote TEXT, ShortFootnote TEXT,
                Bibliography TEXT, Fields BLOB, UTCModDate FLOAT, CitationName TEXT);
            CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER,
                OwnerType INTEGER, OwnerID INTEGER, SortOrder INTEGER, Quality TEXT,
                IsPrivate INTEGER, Flags INTEGER, UTCModDate FLOAT);
            INSERT INTO SourceTable VALUES (589, 6);
            INSERT INTO EventTable VALUES (1, 2, 0, 7), (2, 1, 0, 7);
        """)
        conn.commit()
        conn.close()
        patcher = mock.patch.object(freebmd_death_citation, "windows_file_modified",
                                    return_value=date(2019, 2, 3))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(freebmd_death_citation.main, str(self.db), "--event", "1",
                                  "--text", TEXT, "--scan", SCAN)
        self.assertEqual(code, 0)
        self.assertIn("   SpecificItem: entry for John Smith, age 60, Medway, vol. 2a, p. 383\n", out)
        self.assertIn("   AccessDate: 3 February 2019\n", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply_creates_citation_and_link(self):
        code, out = self.run_main(freebmd_death_citation.main, str(self.db), "--event", "1",
                                  "--text", TEXT, "--scan", SCAN, "--apply")
        self.assertEqual(code, 0)
        self.assertIn("Applied: citation C1 on E1.", out)
        conn = sqlite3.connect(self.db)
        text, fields, name = conn.execute(
            "SELECT ActualText, Fields, CitationName FROM CitationTable WHERE CitationID = 1").fetchone()
        link = conn.execute(
            "SELECT CitationID, OwnerType, OwnerID, SortOrder, Quality FROM CitationLinkTable").fetchone()
        conn.close()
        self.assertEqual(text, "Deaths Jun 1910\r\nSMITH\tJohn\t60\tMedway\t2a\t383")
        self.assertEqual(read_fields(fields)["Citing"],
                         "General Register Office, Deaths registered in April, May, and June 1910")
        self.assertTrue(name.startswith("3 February 2019; entry for John Smith"))
        self.assertEqual(link, (1, 2, 1, 0, "PIX"))

    def test_refuses_an_event_that_is_not_a_death(self):
        code, out = self.run_main(freebmd_death_citation.main, str(self.db), "--event", "2",
                                  "--text", TEXT, "--scan", SCAN)
        self.assertEqual(code, 1)
        self.assertIn("E2 is not a person's Death event", out)

    def test_no_arguments_prints_usage(self):
        code, out = self.run_main(freebmd_death_citation.main)
        self.assertEqual(code, 2)
        self.assertIn("Usage: python freebmd_death_citation.py", out)


if __name__ == "__main__":
    unittest.main()
