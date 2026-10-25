import sqlite3
import unittest

from support import ScriptTestCase

import merge_places

SETUP_SQL = """
CREATE TABLE PlaceTable (PlaceID INTEGER PRIMARY KEY, PlaceType INTEGER, Name TEXT, MasterID INTEGER,
    Note TEXT, Latitude INTEGER, Longitude INTEGER, UTCModDate FLOAT);
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, PlaceID INTEGER, SiteID INTEGER, UTCModDate FLOAT);
CREATE TABLE FANTable (FanID INTEGER PRIMARY KEY, PlaceID INTEGER, SiteID INTEGER, UTCModDate FLOAT);
INSERT INTO PlaceTable VALUES
    (1, 0, 'Testham, Exampleshire, England', 0, '', 0, 0, 0),
    (2, 0, 'Testham, Exampleshire, , England', 0, '', 0, 0, 0),
    (3, 2, 'St Peter', 1, '', 0, 0, 0),
    (4, 2, 'St Peter the Apostle', 2, '', 0, 0, 0),
    (5, 2, 'High Street', 2, '', 0, 0, 0),
    (6, 0, 'Noted, England', 0, 'a note', 0, 0, 0);
INSERT INTO EventTable VALUES (1, 2, 4, 0), (2, 2, 0, 0), (3, 1, 3, 0);
INSERT INTO FANTable VALUES (1, 2, 4, 0);
"""


class MergePlacesMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.commit()
        conn.close()

    def rows(self, sql: str) -> list[tuple]:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute(sql).fetchall()
        finally:
            conn.close()

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(merge_places.main, str(self.db), "--merge", "2", "--into", "1")
        self.assertEqual(code, 0)
        self.assertIn("2 facts, 1 FAN rows, 2 place details move", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_merge_details_takes_the_kept_detail_place(self):
        code, _ = self.run_main(merge_places.main, str(self.db), "--merge", "4", "--into", "3", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.rows("SELECT EventID, PlaceID, SiteID FROM EventTable ORDER BY 1"),
                         [(1, 1, 3), (2, 2, 0), (3, 1, 3)])
        self.assertEqual(self.rows("SELECT PlaceID, SiteID FROM FANTable"), [(1, 3)])
        self.assertEqual(self.rows("SELECT PlaceID FROM PlaceTable WHERE PlaceID = 4"), [])

    def test_merge_places_moves_facts_and_details(self):
        code, _ = self.run_main(merge_places.main, str(self.db), "--merge", "2", "--into", "1", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.rows("SELECT DISTINCT PlaceID FROM EventTable"), [(1,)])
        self.assertEqual(self.rows("SELECT PlaceID FROM PlaceTable WHERE MasterID = 1 ORDER BY 1"), [(3,), (4,), (5,)])
        self.assertEqual(self.rows("SELECT PlaceID FROM PlaceTable WHERE PlaceID = 2"), [])

    def test_refusals(self):
        for merge, into, reason in (("3", "1", "one is a place"), ("6", "1", "note or a map position"),
                                    ("3", "3", "two different")):
            code, out = self.run_main(merge_places.main, str(self.db), "--merge", merge, "--into", into, "--apply")
            self.assertEqual(code, 1)
            self.assertIn(reason, out)
        self.assertEqual(len(self.rows("SELECT PlaceID FROM PlaceTable")), 6)


if __name__ == "__main__":
    unittest.main()
