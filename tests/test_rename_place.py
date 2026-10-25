import sqlite3
import unittest

from support import ScriptTestCase

import rename_place

SETUP_SQL = """
CREATE TABLE PlaceTable (PlaceID INTEGER PRIMARY KEY, PlaceType INTEGER, Name TEXT, MasterID INTEGER,
    Reverse TEXT, UTCModDate FLOAT);
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, PlaceID INTEGER, SiteID INTEGER);
INSERT INTO PlaceTable VALUES
    (1, 0, 'Testham, Wrongshire, England', 0, 'England, Wrongshire, Testham', 0),
    (2, 0, 'Otherton, Exampleshire, England', 0, 'England, Exampleshire, Otherton', 0),
    (3, 2, 'St Peter', 1, 'St Peter', 0),
    (4, 2, 'St Paul', 1, NULL, 0);
INSERT INTO EventTable VALUES (1, 1, 3), (2, 1, 0);
"""


class RenamePlaceMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.commit()
        conn.close()

    def place(self, pid: int) -> tuple:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT Name, Reverse FROM PlaceTable WHERE PlaceID = ?", (pid,)).fetchone()
        finally:
            conn.close()

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(rename_place.main, str(self.db), "--place", "1", "--name",
                                  "Testham, Exampleshire, England")
        self.assertEqual(code, 0)
        self.assertIn("used by 2 facts", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_place_renamed_with_reversed_sort_name(self):
        code, _ = self.run_main(rename_place.main, str(self.db), "--place", "1", "--name",
                                "Testham, Exampleshire, England", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.place(1), ("Testham, Exampleshire, England", "England, Exampleshire, Testham"))

    def test_detail_sort_name_follows_only_when_it_held_the_name(self):
        self.run_main(rename_place.main, str(self.db), "--place", "3", "--name", "St Peter's", "--apply")
        self.run_main(rename_place.main, str(self.db), "--place", "4", "--name", "St Paul's", "--apply")
        self.assertEqual(self.place(3), ("St Peter's", "St Peter's"))
        self.assertEqual(self.place(4), ("St Paul's", None))

    def test_refuses_a_name_in_use(self):
        code, out = self.run_main(rename_place.main, str(self.db), "--place", "4", "--name", "St Peter", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("already used by L3", out)
        self.assertEqual(self.place(4), ("St Paul", None))


if __name__ == "__main__":
    unittest.main()
