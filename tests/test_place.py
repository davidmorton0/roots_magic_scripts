import unittest

from support import ScriptTestCase

import place

EXTRA = """
INSERT INTO PlaceTable (PlaceID, PlaceType, Name, Abbrev, Normalized, MasterID, Note, Reverse) VALUES
    (1, 0, 'Ilkeston, Derbyshire, England', '', '', 0, '', 'England, Derbyshire, Ilkeston'),
    (2, 2, 'Church', '', '', 1, '', 'Church'),
    (3, 0, 'Unused, Kent', '', '', 0, 'n', 'Kent, Unused'),
    (4, 2, 'Hall', '', '', 1, '', '');
INSERT INTO EventTable (EventID, EventType, OwnerType, OwnerID, PlaceID, SiteID) VALUES (1, 1, 0, 1, 1, 2);
"""


class PlaceMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.use_full_schema(EXTRA)

    def run_place(self, *args: str) -> tuple[int, str]:
        return self.run_main(place.main, str(self.db), *args)

    def test_get(self):
        code, out = self.run_place("get", "2")
        self.assertEqual(code, 0)
        self.assertIn("L2  'Church'  (PlaceType 2, under L1 'Ilkeston, Derbyshire, England')", out)
        self.assertIn("uses: facts 1, FAN rows 0, place details 0", out)
        code, out = self.run_place("get", "--name", "ilkeston")
        self.assertIn("uses: facts 1, FAN rows 0, place details 2", out)
        self.assertEqual(self.run_place("get", "99")[0], 1)
        self.assertEqual(self.run_place("get", "--name", "zzz")[0], 1)

    def test_create_place_and_detail(self):
        before = self.db.read_bytes()
        args = ("create", "--name", "Leeds, Yorkshire, England", "--set", "Note=n")
        self.assertEqual((self.run_place(*args)[0], self.db.read_bytes()), (0, before))
        code, out = self.run_place(*args, "--apply")
        self.assertEqual(code, 0)
        self.assertIn("Applied: place L5.", out)
        self.assertEqual(self.query("SELECT PlaceType, Name, Normalized, MasterID, Note, Reverse, Latitude, fsID"
                                    " FROM PlaceTable WHERE PlaceID = 5"),
                         [(0, "Leeds, Yorkshire, England", "", 0, "n", "England, Yorkshire, Leeds", 0, 0)])
        code, _ = self.run_place("create", "--name", "Vicarage", "--master", "5", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.query("SELECT PlaceType, MasterID, Reverse FROM PlaceTable WHERE PlaceID = 6"),
                         [(2, 5, "Vicarage")])

    def test_create_refusals(self):
        code, out = self.run_place("create", "--name", "ilkeston, derbyshire, england", "--set", "Bad=1")
        self.assertEqual(code, 1)
        self.assertIn("already used by L1", out)
        self.assertIn("--set 'Bad' is not one of", out)
        code, out = self.run_place("create", "--name", "church", "--master", "1")
        self.assertIn("already used by L2", out)
        code, out = self.run_place("create", "--name", "Pew", "--master", "2")
        self.assertIn("L2 is not a place", out)

    def test_edit_place_and_detail(self):
        code, out = self.run_place("edit", "1", "--name", "Ilkeston, Derbys, England", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.query("SELECT Name, Reverse FROM PlaceTable WHERE PlaceID = 1"),
                         [("Ilkeston, Derbys, England", "England, Derbys, Ilkeston")])
        self.run_place("edit", "2", "--name", "St Mary's", "--set", "Abbrev=SM", "--apply")
        self.assertEqual(self.query("SELECT Name, Reverse, Abbrev FROM PlaceTable WHERE PlaceID = 2"),
                         [("St Mary's", "St Mary's", "SM")])
        self.run_place("edit", "4", "--name", "Great Hall", "--apply")
        self.assertEqual(self.query("SELECT Reverse FROM PlaceTable WHERE PlaceID = 4"), [("",)])

    def test_edit_refusals(self):
        code, out = self.run_place("edit", "4", "--name", "Church")
        self.assertEqual(code, 1)
        self.assertIn("already used by L2", out)
        self.assertEqual(self.run_place("edit", "3", "--name", "Unused, Kent")[0], 0)
        self.assertEqual(self.run_place("edit", "99", "--name", "x")[0], 1)
        self.assertEqual(self.run_place("edit", "3")[0], 1)

    def test_delete(self):
        code, out = self.run_place("delete", "1", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("still used: {'facts': 1, 'place details': 2}", out)
        before = self.db.read_bytes()
        self.assertEqual((self.run_place("delete", "3")[0], self.db.read_bytes()), (0, before))
        self.assertEqual(self.run_place("delete", "3", "--apply")[0], 0)
        self.assertEqual(self.query("SELECT PlaceID FROM PlaceTable WHERE PlaceID = 3"), [])
        self.assertEqual(self.run_place("delete", "99")[0], 1)


if __name__ == "__main__":
    unittest.main()
