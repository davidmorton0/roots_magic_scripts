import sqlite3
import unittest

from support import ScriptTestCase

import source_people

SETUP_SQL = """
CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, Name TEXT);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER);
CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER, OwnerType INTEGER,
    OwnerID INTEGER);
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, EventType INTEGER, OwnerType INTEGER, OwnerID INTEGER,
    Date TEXT, PlaceID INTEGER, SiteID INTEGER);
CREATE TABLE FamilyTable (FamilyID INTEGER PRIMARY KEY, FatherID INTEGER, MotherID INTEGER);
CREATE TABLE ChildTable (RecID INTEGER PRIMARY KEY, ChildID INTEGER, FamilyID INTEGER);
CREATE TABLE PlaceTable (PlaceID INTEGER PRIMARY KEY, Name TEXT);
INSERT INTO SourceTable VALUES (7, 'Marriages - Test'), (8, 'Births - Test');
INSERT INTO CitationTable VALUES (30, 7), (31, 7), (40, 8);
INSERT INTO FamilyTable VALUES (5, 1, 2), (6, 3, 0);
INSERT INTO ChildTable (ChildID, FamilyID) VALUES (1, 6);
INSERT INTO PlaceTable VALUES (10, 'Testham, England'), (11, 'St Peter');
INSERT INTO EventTable VALUES
    (20, 300, 1, 5, 'D.+18800101..+00000000..', 10, 11),
    (21, 1, 0, 1, 'D.+18500000..+00000000..', 10, 0),
    (22, 2, 0, 1, 'D.+19100000..+00000000..', 0, 0);
INSERT INTO CitationLinkTable (CitationID, OwnerType, OwnerID) VALUES
    (30, 2, 20), (30, 1, 5), (31, 2, 21), (40, 2, 21);
"""


class SourcePeopleMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.commit()
        conn.close()

    def test_lists_people_with_facts_parents_and_marriages(self):
        before = self.db.read_bytes()
        code, out = self.run_main(source_people.main, str(self.db), "7")
        self.assertEqual(code, 0)
        self.assertIn("S7: 2 people", out)
        self.assertEqual(self.db.read_bytes(), before)
        text = self.output_path("source_7_people").read_text(encoding="utf-8")
        for line in (
            "P1 John smith (this source: C30, C31)",
            "   Birth: D.+18500000..+00000000.. Testham, England [E21; C31, C40]",
            "   Death: D.+19100000..+00000000.. no place [E22; not cited]",
            "   parents F6: P3 Albert Brown, Jr & ?",
            "   family F5 with P2 Dr Mary Brown",
            "      Marriage: D.+18800101..+00000000.. St Peter, Testham, England [E20; C30]",
            "P2 Dr Mary Brown (this source: C30)",
        ):
            self.assertIn(line + "\n", text)

    def test_unknown_source(self):
        code, out = self.run_main(source_people.main, str(self.db), "9")
        self.assertEqual(code, 1)
        self.assertIn("No source S9", out)


if __name__ == "__main__":
    unittest.main()
