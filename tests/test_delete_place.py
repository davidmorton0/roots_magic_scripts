import sqlite3
import unittest

from support import ScriptTestCase

import delete_place

SETUP_SQL = """
CREATE TABLE PlaceTable (PlaceID INTEGER PRIMARY KEY, Name TEXT, MasterID INTEGER);
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, PlaceID INTEGER, SiteID INTEGER);
CREATE TABLE FANTable (FanID INTEGER PRIMARY KEY, PlaceID INTEGER, SiteID INTEGER);
INSERT INTO PlaceTable VALUES (1, 'Testham', 0), (2, 'Unused', 0), (3, 'St Peter', 1), (4, 'Fan place', 0),
    (5, 'Has detail', 0), (6, 'Detail', 5);
INSERT INTO EventTable VALUES (1, 1, 3);
INSERT INTO FANTable VALUES (1, 4, 0);
"""


class DeletePlaceMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.commit()
        conn.close()

    def places(self) -> list[int]:
        conn = sqlite3.connect(self.db)
        try:
            return [r[0] for r in conn.execute("SELECT PlaceID FROM PlaceTable ORDER BY 1")]
        finally:
            conn.close()

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(delete_place.main, str(self.db), "--place", "2")
        self.assertEqual(code, 0)
        self.assertIn("Delete L2 'Unused'", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply_deletes_unused(self):
        code, _ = self.run_main(delete_place.main, str(self.db), "--place", "2", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.places(), [1, 3, 4, 5, 6])

    def test_refuses_used_places(self):
        for place, reason in (("1", "'facts': 1"), ("3", "'facts': 1"), ("4", "'FAN rows': 1"),
                              ("5", "'place details': 1"), ("9", "no place")):
            code, out = self.run_main(delete_place.main, str(self.db), "--place", place, "--apply")
            self.assertEqual(code, 1)
            self.assertIn(reason, out)
        self.assertEqual(len(self.places()), 6)


if __name__ == "__main__":
    unittest.main()
