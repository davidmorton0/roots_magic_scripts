import sqlite3
import unittest

from support import ScriptTestCase

import set_event_place

SETUP_SQL = """
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, EventType INTEGER, OwnerType INTEGER, OwnerID INTEGER,
    PlaceID INTEGER, SiteID INTEGER, UTCModDate FLOAT);
CREATE TABLE PlaceTable (PlaceID INTEGER PRIMARY KEY, PlaceType INTEGER, Name TEXT, Abbrev TEXT, Normalized TEXT,
    Latitude INTEGER, Longitude INTEGER, LatLongExact INTEGER, MasterID INTEGER, Note TEXT, Reverse TEXT,
    fsID INTEGER, anID INTEGER, UTCModDate FLOAT);
INSERT INTO PlaceTable (PlaceID, PlaceType, Name, MasterID) VALUES (1, 0, 'Townton', 0), (2, 2, '9 High Street', 1),
    (3, 0, 'Cityham', 0), (4, 2, 'General Hospital', 3);
INSERT INTO EventTable VALUES (20, 2, 0, 5, 1, 2, 1.0);
"""


class SetEventPlaceMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.commit()
        conn.close()

    def place(self) -> tuple:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT PlaceID, SiteID FROM EventTable WHERE EventID = 20").fetchone()
        finally:
            conn.close()

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(set_event_place.main, str(self.db), "--event", "20", "--place", "3",
                                  "--site", "4")
        self.assertEqual(code, 0)
        self.assertIn("L1 Townton / L2 9 High Street -> L3 Cityham / L4 General Hospital", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply_sets_place_and_site(self):
        code, _ = self.run_main(set_event_place.main, str(self.db), "--event", "20", "--place", "3", "--site", "4",
                                "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.place(), (3, 4))

    def test_apply_without_site(self):
        code, _ = self.run_main(set_event_place.main, str(self.db), "--event", "20", "--place", "3", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.place(), (3, 0))

    def test_new_site_made_or_reused(self):
        code, out = self.run_main(set_event_place.main, str(self.db), "--event", "20", "--place", "3",
                                  "--new-site", "Old People's Home")
        self.assertEqual(code, 0)
        self.assertIn("-> L3 Cityham / new detail Old People's Home", out)
        self.assertEqual(self.place(), (1, 2))
        code, _ = self.run_main(set_event_place.main, str(self.db), "--event", "20", "--place", "3",
                                "--new-site", "Old People's Home", "--apply")
        self.assertEqual(code, 0)
        conn = sqlite3.connect(self.db)
        try:
            new = conn.execute("SELECT PlaceID, PlaceType, MasterID, Reverse FROM PlaceTable WHERE Name = ?",
                               ("Old People's Home",)).fetchall()
        finally:
            conn.close()
        self.assertEqual(new, [(5, 2, 3, "Old People's Home")])
        self.assertEqual(self.place(), (3, 5))
        code, out = self.run_main(set_event_place.main, str(self.db), "--event", "20", "--place", "3",
                                  "--new-site", "General Hospital")
        self.assertIn("-> L3 Cityham / L4 General Hospital", out)

    def test_refused(self):
        code, out = self.run_main(set_event_place.main, str(self.db), "--event", "20", "--place", "3",
                                  "--site", "2")
        self.assertEqual(code, 1)
        self.assertIn("L2 is not a detail under L3", out)
        code, out = self.run_main(set_event_place.main, str(self.db), "--event", "99", "--place", "2")
        self.assertEqual(code, 1)
        self.assertIn("E99 not found; L2 is not a place", out)
        self.assertEqual(self.place(), (1, 2))


if __name__ == "__main__":
    unittest.main()
