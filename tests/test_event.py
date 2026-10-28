import unittest

from support import ScriptTestCase

import event
import rmutils

BLANK = "0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0"
DATE = "D.+18860315..+00000000.."
EXTRA = f"""
INSERT INTO PersonTable VALUES (1, 'U1', 0, 0, 0, {BLANK}, '', 1.0);
INSERT INTO FamilyTable (FamilyID, FatherID, MotherID) VALUES (7, 1, 0);
INSERT INTO FactTypeTable VALUES (1, 0, 'Birth'), (2, 0, 'Death'), (300, 1, 'Marriage');
INSERT INTO PlaceTable (PlaceID, PlaceType, Name, MasterID) VALUES (5, 0, 'Leeds', 0), (6, 2, 'Church', 5),
    (8, 0, 'York', 0);
INSERT INTO EventTable (EventID, EventType, OwnerType, OwnerID, FamilyID, PlaceID, SiteID, Date, SortDate,
    IsPrimary, Details, UTCModDate) VALUES (10, 1, 0, 1, 0, 5, 6, '{DATE}', 5, 1, 'd', 1.0),
    (11, 2, 0, 1, 0, 0, 0, '.', 9223372036854775807, 1, '', 1.0),
    (12, 300, 1, 7, 0, 0, 0, '.', 9223372036854775807, 1, '', 1.0);
INSERT INTO CitationLinkTable VALUES (1, 3, 2, 10, 0, 'PIX', 0, 0, 1.0);
INSERT INTO WitnessTable VALUES (1, 12, 1, 0, 39);
"""


class EventMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.use_full_schema(EXTRA)

    def run_event(self, *args: str) -> tuple[int, str]:
        return self.run_main(event.main, str(self.db), *args)

    def test_get(self):
        code, out = self.run_event("get", "10")
        self.assertEqual(code, 0)
        self.assertIn("E10  Birth (fact 1)  person 1", out)
        self.assertIn("place: L5 Leeds / L6 Church", out)
        self.assertIn("citations 1, media 0, witnesses 0", out)
        code, out = self.run_event("get", "--owner", "person:1", "--type", "2")
        self.assertIn("E11  Death", out)
        self.assertNotIn("E10", out)
        self.assertIn("E12  Marriage", self.run_event("get", "--owner", "family:7")[1])
        self.assertEqual(self.run_event("get", "99")[0], 1)
        self.assertEqual(self.run_event("get", "--owner", "person:9")[0], 1)

    def test_create(self):
        before = self.db.read_bytes()
        args = ("create", "--owner", "person:1", "--type", "1", "--date", DATE, "--place", "5", "--site", "6",
                "--set", "Details=born at home")
        self.assertEqual((self.run_event(*args)[0], self.db.read_bytes()), (0, before))
        code, out = self.run_event(*args, "--apply")
        self.assertEqual(code, 0)
        self.assertIn("Applied: event E13.", out)
        self.assertEqual(self.query("SELECT EventType, OwnerType, OwnerID, FamilyID, PlaceID, SiteID, Date, SortDate,"
                                    " IsPrimary, Details, Note FROM EventTable WHERE EventID = 13"),
                         [(1, 0, 1, 0, 5, 6, DATE, rmutils.sort_date(DATE), 0, "born at home", "")])

    def test_create_primary_and_defaults(self):
        code, _ = self.run_event("create", "--owner", "family:7", "--type", "300", "--apply")
        self.assertEqual(code, 0)
        code, _ = self.run_event("create", "--owner", "person:1", "--type", "2", "--primary", "1", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.query("SELECT IsPrimary, Date, SortDate, PlaceID FROM EventTable WHERE EventID = 13"),
                         [(0, ".", 9223372036854775807, 0)])
        self.assertEqual(self.query("SELECT IsPrimary FROM EventTable WHERE EventID = 14"), [(1,)])
        code, _ = self.run_event("create", "--owner", "person:1", "--type", "1", "--apply")
        self.assertEqual(self.query("SELECT IsPrimary FROM EventTable WHERE EventID = 15"), [(0,)])

    def test_create_refusals(self):
        code, out = self.run_event("create", "--owner", "person:9", "--type", "300", "--date", "D.+1886",
                                   "--place", "6", "--site", "6", "--set", "Bad=1", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("person 9 not found", out)
        self.assertIn("fact type 300 is not a person fact", out)
        self.assertIn("SortDate not known", out)
        self.assertIn("L6 is not a place", out)
        self.assertIn("--set 'Bad' is not one of", out)
        code, out = self.run_event("create", "--owner", "bad", "--type", "77", "--apply")
        self.assertIn("is not KIND:ID", out)
        self.assertEqual(self.query("SELECT COUNT(*) FROM EventTable"), [(3,)])

    def test_edit(self):
        code, out = self.run_event("edit", "10", "--date", "DB+18860400..+00000000..", "--place", "8", "--site", "0",
                                   "--set", "Note=n", "--primary", "0", "--apply")
        self.assertEqual(code, 0)
        row = self.query("SELECT Date, SortDate, PlaceID, SiteID, Note, IsPrimary, UTCModDate FROM EventTable"
                         " WHERE EventID = 10")[0]
        self.assertEqual(row[:6], ("DB+18860400..+00000000..", rmutils.sort_date("DB+18860400..+00000000.."), 8, 0,
                                   "n", 0))
        self.assertGreater(row[6], 1.0)

    def test_edit_refusals(self):
        code, out = self.run_event("edit", "10", "--place", "8")
        self.assertEqual(code, 1)
        self.assertIn("L6 is not a detail under L8", out)
        code, out = self.run_event("edit", "10", "--type", "300", "--date", "bad")
        self.assertIn("fact type 300 is not a person fact", out)
        self.assertIn("SortDate not known", out)
        self.assertEqual(self.run_event("edit", "99", "--set", "Note=x")[0], 1)
        self.assertEqual(self.run_event("edit", "10")[0], 1)

    def test_delete(self):
        code, out = self.run_event("delete", "10", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("1 citation links; give --with-links", out)
        code, out = self.run_event("delete", "12", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("1 witness entries", out)
        before = self.db.read_bytes()
        self.assertEqual((self.run_event("delete", "10", "--with-links")[0], self.db.read_bytes()), (0, before))
        code, _ = self.run_event("delete", "10", "--with-links", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.query("SELECT EventID FROM EventTable ORDER BY 1"), [(11,), (12,)])
        self.assertEqual(self.query("SELECT COUNT(*) FROM CitationLinkTable"), [(0,)])
        self.assertEqual(self.run_event("delete", "99")[0], 1)


if __name__ == "__main__":
    unittest.main()
