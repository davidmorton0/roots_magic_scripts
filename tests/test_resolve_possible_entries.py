import sqlite3
import unittest

from support import ScriptTestCase

import resolve_possible_entries

NOTE = "Confirmed by the GRO online index: mother's maiden name Fenwick."
SETUP_SQL = """
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, CitationName TEXT, Comments TEXT,
    UTCModDate FLOAT);
CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER, OwnerType INTEGER,
    OwnerID INTEGER);
CREATE TABLE MediaLinkTable (LinkID INTEGER PRIMARY KEY, MediaID INTEGER, OwnerType INTEGER,
    OwnerID INTEGER, UTCModDate FLOAT);
INSERT INTO CitationTable VALUES (10, 'p. 474', 'One of two possible records', 1.0),
    (11, 'p. 364', 'One of two possible records', 1.0), (12, 'other', '', 1.0);
INSERT INTO CitationLinkTable VALUES (100, 10, 2, 5), (101, 11, 2, 5), (102, 12, 2, 9);
INSERT INTO MediaLinkTable VALUES (200, 1, 4, 10, 1.0), (201, 1, 4, 11, 1.0), (202, 2, 4, 10, 1.0);
"""


class ResolvePossibleEntriesMainTest(ScriptTestCase):
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
        code, out = self.run_main(resolve_possible_entries.main, str(self.db),
                                  "--keep", "11", "--drop", "10", "--note", NOTE)
        self.assertEqual(code, 0)
        self.assertIn("media moved to C11 [2]", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply(self):
        code, _ = self.run_main(resolve_possible_entries.main, str(self.db),
                                "--keep", "11", "--drop", "10", "--note", NOTE, "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.query("SELECT CitationID, Comments FROM CitationTable ORDER BY 1"),
                         [(11, NOTE), (12, "")])
        self.assertEqual(self.query("SELECT LinkID FROM CitationLinkTable ORDER BY 1"), [(101,), (102,)])
        self.assertEqual(self.query("SELECT LinkID, MediaID, OwnerID FROM MediaLinkTable ORDER BY 1"),
                         [(201, 1, 11), (202, 2, 11)])

    def test_refuses_when_linked_elsewhere(self):
        code, out = self.run_main(resolve_possible_entries.main, str(self.db),
                                  "--keep", "11", "--drop", "12", "--note", NOTE)
        self.assertEqual(code, 1)
        self.assertIn("resolve by hand", out)


if __name__ == "__main__":
    unittest.main()
