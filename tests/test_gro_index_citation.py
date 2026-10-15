import sqlite3
import unittest

from support import ScriptTestCase

import gro_index_citation
from rmutils import read_fields

SETUP_SQL = """
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, EventType INTEGER, OwnerType INTEGER);
CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, Name TEXT, RefNumber TEXT, ActualText TEXT,
    Comments TEXT, IsPrivate INTEGER, TemplateID INTEGER, Fields BLOB, UTCModDate FLOAT);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER, Comments TEXT,
    ActualText TEXT, RefNumber TEXT, Footnote TEXT, ShortFootnote TEXT, Bibliography TEXT,
    Fields BLOB, UTCModDate FLOAT, CitationName TEXT);
CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER, OwnerType INTEGER,
    OwnerID INTEGER, SortOrder INTEGER, Quality TEXT, IsPrivate INTEGER, Flags INTEGER,
    UTCModDate FLOAT);
INSERT INTO EventTable VALUES (2740, 1, 0), (9, 1006, 0);
"""
ARGS = ["--event", "2740", "--name", "Henry Capper", "--district", "Sheffield", "--volume", "09C",
        "--page", "364", "--mmn", "Crossland", "--year", "1871", "--quarter", "2",
        "--accessed", "15 October 2026", "--text", "CAPPER, HENRY CROSSLAND"]


class GroIndexCitationMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.commit()
        conn.close()

    def query(self, sql: str) -> list[tuple]:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute(sql).fetchall()
        finally:
            conn.close()

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(gro_index_citation.main, str(self.db), *ARGS)
        self.assertEqual(code, 0)
        self.assertIn("New source 'Birth Register - UK - GRO'", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply_twice_reuses_source(self):
        self.run_main(gro_index_citation.main, str(self.db), *ARGS, "--apply")
        code, out = self.run_main(gro_index_citation.main, str(self.db), *ARGS, "--apply")
        self.assertEqual(code, 0)
        self.assertIn("exists", out)
        self.assertEqual(self.query("SELECT COUNT(*) FROM SourceTable"), [(1,)])
        name, blob, text = self.query("SELECT CitationName, Fields, ActualText FROM CitationTable")[0]
        self.assertEqual(read_fields(blob)["SpecificItem"],
                         "entry for Henry Capper, Sheffield, vol. 09C, p. 364, mother's maiden name Crossland")
        self.assertEqual(text, "CAPPER, HENRY CROSSLAND")
        self.assertTrue(name.startswith("15 October 2026; entry for Henry Capper"))
        self.assertEqual(self.query("SELECT OwnerType, OwnerID, Quality, SortOrder FROM CitationLinkTable LIMIT 1"),
                         [(2, 2740, "PIX", None)])

    def test_refuses_non_birth_event(self):
        args = list(ARGS)
        args[1] = "9"
        code, out = self.run_main(gro_index_citation.main, str(self.db), *args)
        self.assertEqual(code, 1)
        self.assertIn("is not a person's Birth event", out)


if __name__ == "__main__":
    unittest.main()
