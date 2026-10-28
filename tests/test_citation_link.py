import sqlite3
import unittest

from support import ScriptTestCase

import citation_link

SETUP_SQL = """
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY);
INSERT INTO CitationTable VALUES (5), (6);
CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER, OwnerType INTEGER, OwnerID INTEGER,
    SortOrder INTEGER, Quality TEXT, IsPrivate INTEGER, Flags INTEGER, UTCModDate FLOAT);
INSERT INTO CitationLinkTable VALUES (1, 5, 2, 20, 0, '~~~', 0, 0, 1.0), (2, 5, 0, 1, 0, 'PIX', 0, 0, 1.0);
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY);
CREATE TABLE FamilyTable (FamilyID INTEGER PRIMARY KEY);
INSERT INTO EventTable VALUES (20), (21);
INSERT INTO FamilyTable VALUES (30);
"""


class CitationLinkMainTest(ScriptTestCase):
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

    def run_link(self, *args: str) -> tuple[int, str]:
        return self.run_main(citation_link.main, str(self.db), *args)

    def test_get(self):
        code, out = self.run_link("get", "--citation", "5")
        self.assertEqual(code, 0)
        self.assertIn("L1: C5 -> event 20 ~~~", out)
        self.assertIn("L2: C5 -> person 1 PIX", out)
        code, out = self.run_link("get", "--owner", "event:20")
        self.assertIn("L1: C5", out)
        self.assertEqual(self.run_link("get", "99")[0], 1)
        self.assertEqual(self.run_link("get", "--owner", "event:21")[0], 1)
        self.assertEqual(self.run_link("get", "--owner", "bad")[0], 1)

    def test_create(self):
        before = self.db.read_bytes()
        code, out = self.run_link("create", "--citation", "6", "--owner", "family:30", "--quality", "SIX")
        self.assertEqual((code, self.db.read_bytes()), (0, before))
        self.assertIn("Dry run", out)
        code, out = self.run_link("create", "--citation", "6", "--owner", "family:30", "--quality", "SIX", "--apply")
        self.assertEqual(code, 0)
        self.assertIn("Applied: link L3.", out)
        self.assertEqual(self.query("SELECT CitationID, OwnerType, OwnerID, SortOrder, Quality, IsPrivate, Flags"
                                    " FROM CitationLinkTable WHERE LinkID = 3"), [(6, 1, 30, 0, "SIX", 0, 0)])

    def test_create_refusals(self):
        code, out = self.run_link("create", "--citation", "5", "--owner", "event:20", "--quality", "PIX", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("event 20 already has C5", out)
        code, out = self.run_link("create", "--citation", "9", "--owner", "event:99", "--quality", "PD", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("C9 not found", out)
        self.assertIn("event 99 not found", out)
        self.assertIn("quality 'PD' is not three characters", out)
        self.assertEqual(self.query("SELECT COUNT(*) FROM CitationLinkTable"), [(2,)])

    def test_edit(self):
        code, out = self.run_link("edit", "1", "--quality", "PIX", "--private", "1", "--apply")
        self.assertEqual(code, 0)
        row = self.query("SELECT Quality, IsPrivate, UTCModDate FROM CitationLinkTable WHERE LinkID = 1")[0]
        self.assertEqual(row[:2], ("PIX", 1))
        self.assertGreater(row[2], 1.0)
        self.assertEqual(self.query("SELECT Quality FROM CitationLinkTable WHERE LinkID = 2"), [("PIX",)])
        code, out = self.run_link("edit", "1", "99", "--quality", "XXX", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("quality 'XXX' is not three characters", out)
        self.assertIn("L99 not found", out)
        self.assertEqual(self.run_link("edit", "1")[0], 1)

    def test_delete(self):
        before = self.db.read_bytes()
        self.assertEqual(self.run_link("delete", "1")[0], 0)
        self.assertEqual(self.db.read_bytes(), before)
        self.assertEqual(self.run_link("delete", "1", "99", "--apply")[0], 1)
        code, out = self.run_link("delete", "1", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.query("SELECT LinkID FROM CitationLinkTable"), [(2,)])


if __name__ == "__main__":
    unittest.main()
