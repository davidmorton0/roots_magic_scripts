import sqlite3
import unittest

from support import ScriptTestCase

import merge_duplicate_citations

SETUP_SQL = """
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER, CitationName TEXT,
    Fields BLOB, ActualText TEXT, Comments TEXT);
CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER,
    OwnerType INTEGER, OwnerID INTEGER, UTCModDate FLOAT);
CREATE TABLE MediaLinkTable (LinkID INTEGER PRIMARY KEY, MediaID INTEGER,
    OwnerType INTEGER, OwnerID INTEGER, UTCModDate FLOAT);
INSERT INTO CitationTable VALUES
    -- 10 and 11: same entry, same event; 11's text has spaces instead of tabs
    (10, 583, 'a', X'3c526f6f742f3e', 'Births Mar 1886' || char(10) || 'Doe' || char(9) || 'Jane', ''),
    (11, 583, 'a', X'3c526f6f742f3e', 'Births Mar 1886' || char(10) || 'Doe Jane', ''),
    -- 12: same fields but a different comment: not a duplicate
    (12, 583, 'a', X'3c526f6f742f3e', 'Births Mar 1886' || char(10) || 'Doe Jane', 'one of two'),
    -- 20 and 21: same content but no shared record: not duplicates
    (20, 583, 'b', X'3c526f6f742f3e', 'x', ''),
    (21, 583, 'b', X'3c526f6f742f3e', 'x', ''),
    -- 30 and 31: duplicates in another source, not selected
    (30, 999, 'c', X'3c526f6f742f3e', 'y', ''),
    (31, 999, 'c', X'3c526f6f742f3e', 'y', '');
INSERT INTO CitationLinkTable (LinkID, CitationID, OwnerType, OwnerID) VALUES
    (100, 10, 2, 1), (101, 11, 2, 1), (102, 11, 0, 7), (103, 12, 2, 1),
    (104, 20, 2, 2), (105, 21, 2, 3), (106, 30, 2, 4), (107, 31, 2, 4);
INSERT INTO MediaLinkTable (LinkID, MediaID, OwnerType, OwnerID) VALUES
    (200, 1, 4, 10), (201, 1, 4, 11), (202, 2, 4, 11);
"""


class MergeDuplicateCitationsMainTest(ScriptTestCase):
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
        code, out = self.run_main(merge_duplicate_citations.main, str(self.db), "--source", "583")
        self.assertEqual(code, 0)
        self.assertIn("1 duplicate groups; 1 citations to delete; 2 links to move", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply_keeps_lowest_and_moves_extra_links(self):
        code, out = self.run_main(
            merge_duplicate_citations.main, str(self.db), "--source", "583", "--apply"
        )
        self.assertEqual(code, 0)
        self.assertEqual(
            self.query("SELECT CitationID FROM CitationTable ORDER BY CitationID"),
            [(10,), (12,), (20,), (21,), (30,), (31,)],
        )
        self.assertEqual(
            self.query("SELECT LinkID, CitationID, OwnerType, OwnerID FROM CitationLinkTable ORDER BY LinkID"),
            [(100, 10, 2, 1), (102, 10, 0, 7), (103, 12, 2, 1), (104, 20, 2, 2),
             (105, 21, 2, 3), (106, 30, 2, 4), (107, 31, 2, 4)],
        )
        self.assertEqual(
            self.query("SELECT LinkID, MediaID, OwnerID FROM MediaLinkTable ORDER BY LinkID"),
            [(200, 1, 10), (202, 2, 10)],
        )


if __name__ == "__main__":
    unittest.main()
