import sqlite3
import unittest

from support import ScriptTestCase

import delete_source

SETUP_SQL = """
CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, Name TEXT);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER);
CREATE TABLE MediaLinkTable (LinkID INTEGER PRIMARY KEY, OwnerType INTEGER, OwnerID INTEGER);
CREATE TABLE TaskLinkTable (LinkID INTEGER PRIMARY KEY, OwnerType INTEGER, OwnerID INTEGER);
CREATE TABLE URLTable (LinkID INTEGER PRIMARY KEY, OwnerType INTEGER, OwnerID INTEGER);
CREATE TABLE AddressLinkTable (LinkID INTEGER PRIMARY KEY, OwnerType INTEGER, OwnerID INTEGER);
INSERT INTO SourceTable VALUES (590, 'Empty'), (591, 'Used'), (592, 'Has media');
INSERT INTO CitationTable VALUES (1, 591);
INSERT INTO MediaLinkTable VALUES (1, 3, 592);
"""


class DeleteSourceMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.commit()
        conn.close()

    def sources(self) -> list[tuple]:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT SourceID FROM SourceTable ORDER BY 1").fetchall()
        finally:
            conn.close()

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(delete_source.main, str(self.db), "590")
        self.assertEqual(code, 0)
        self.assertIn("Delete S590 'Empty'", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply_deletes_unused(self):
        code, _ = self.run_main(delete_source.main, str(self.db), "590", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.sources(), [(591,), (592,)])

    def test_refuses_used_sources(self):
        for source, kind in (("591", "citations"), ("592", "media")):
            code, out = self.run_main(delete_source.main, str(self.db), source, "--apply")
            self.assertEqual(code, 1)
            self.assertIn(f"'{kind}': 1", out)
        self.assertEqual(len(self.sources()), 3)


if __name__ == "__main__":
    unittest.main()
