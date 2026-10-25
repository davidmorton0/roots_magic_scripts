import sqlite3
import unittest

from support import ScriptTestCase

import link_citation

SETUP_SQL = """
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY);
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, EventType INTEGER, OwnerType INTEGER, OwnerID INTEGER,
    Date TEXT);
CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER, OwnerType INTEGER,
    OwnerID INTEGER, SortOrder INTEGER, Quality TEXT, IsPrivate INTEGER, Flags INTEGER, UTCModDate FLOAT);
INSERT INTO CitationTable VALUES (10);
INSERT INTO EventTable VALUES (20, 1, 0, 2, 'D.+18941228..+00000000..'), (21, 300, 1, 5, '.');
INSERT INTO CitationLinkTable VALUES (1, 10, 2, 21, 0, 'PDX', 0, 0, 1.0);
"""


class LinkCitationMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.commit()
        conn.close()

    def links(self) -> list[tuple]:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT CitationID, OwnerType, OwnerID, Quality, IsPrivate, Flags"
                                " FROM CitationLinkTable ORDER BY LinkID").fetchall()
        finally:
            conn.close()

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(link_citation.main, str(self.db), "--citation", "10", "--event", "20",
                                  "--quality", "SIX")
        self.assertEqual(code, 0)
        self.assertIn("Link C10 -> E20 (fact 1, owner type 0 ID 2, D.+18941228..+00000000..) SIX", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply_adds_link(self):
        code, _ = self.run_main(link_citation.main, str(self.db), "--citation", "10", "--event", "20",
                                "--quality", "SIX", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.links(), [(10, 2, 21, "PDX", 0, 0), (10, 2, 20, "SIX", 0, 0)])

    def test_already_linked_is_refused(self):
        code, out = self.run_main(link_citation.main, str(self.db), "--citation", "10", "--event", "21",
                                  "--quality", "PDX", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("E21 already has C10", out)
        self.assertEqual(len(self.links()), 1)

    def test_missing_rows_and_bad_quality(self):
        code, out = self.run_main(link_citation.main, str(self.db), "--citation", "99", "--event", "98",
                                  "--quality", "SIX")
        self.assertEqual(code, 1)
        self.assertIn("C99 not found; E98 not found", out)
        code, out = self.run_main(link_citation.main, str(self.db), "--citation", "10", "--event", "20",
                                  "--quality", "XYZ")
        self.assertEqual(code, 1)
        self.assertIn("is not three characters", out)


if __name__ == "__main__":
    unittest.main()
