import sqlite3
import unittest

from support import ScriptTestCase

import missing_records
import rmutils

# Invented people. P1 root (smith John, from support), F1 parents P3 + P2 with children P1 and P5;
# F2 P1 + P6 with child P7; F3 parents of the spouse P6 (P8, not followed).
SETUP_SQL = """
INSERT INTO PersonTable VALUES (5, 0), (6, 1), (7, 0), (8, 0);
INSERT INTO NameTable (OwnerID, Surname, Given, IsPrimary) VALUES (5, 'smith', 'Peter', 1), (6, 'Green', 'Ann', 1),
    (7, 'smith', 'Tom', 1), (8, 'Green', 'Sam', 1);
CREATE TABLE ConfigTable (RecID INTEGER PRIMARY KEY, DataRec BLOB);
INSERT INTO ConfigTable VALUES (1, CAST('<Root><RootPerson>1</RootPerson></Root>' AS BLOB));
CREATE TABLE PlaceTable (PlaceID INTEGER PRIMARY KEY, Name TEXT);
INSERT INTO PlaceTable VALUES (1, 'Nottingham, Nottinghamshire, England, United Kingdom'), (2, 'Dublin, Ireland');
CREATE TABLE FamilyTable (FamilyID INTEGER PRIMARY KEY, FatherID INTEGER, MotherID INTEGER);
INSERT INTO FamilyTable VALUES (1, 3, 2), (2, 1, 6), (3, 8, 0);
CREATE TABLE ChildTable (ChildID INTEGER, FamilyID INTEGER, ChildOrder INTEGER);
INSERT INTO ChildTable VALUES (1, 1, 1), (5, 1, 2), (7, 2, 1), (6, 3, 1);
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, EventType INTEGER, OwnerType INTEGER, OwnerID INTEGER,
    Date TEXT, PlaceID INTEGER, IsPrimary INTEGER);
INSERT INTO EventTable VALUES
    (1, 1, 0, 1, 'D.+18500201..+00000000..', 1, 1),
    (2, 29, 0, 1, 'D.+18510330..+00000000..', 1, 1),
    (3, 2, 0, 1, 'D.+19100501..+00000000..', 1, 1),
    (4, 300, 1, 2, 'D.+18750000..+00000000..', 1, 1),
    (5, 1, 0, 2, 'D.+18200000..+00000000..', 1, 1),
    (6, 1, 0, 5, 'D.+18550000..+00000000..', 2, 1),
    (7, 1, 0, 6, 'D.+18520000..+00000000..', 1, 1),
    (8, 1, 0, 7, 'D.+19300000..+00000000..', 1, 1);
CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, Name TEXT);
INSERT INTO SourceTable VALUES (1, 'Birth Register - UK - FreeBMD'), (2, 'Census - England 1851 - Ancestry');
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER);
INSERT INTO CitationTable VALUES (10, 1), (11, 2);
CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER, OwnerType INTEGER, OwnerID INTEGER);
INSERT INTO CitationLinkTable VALUES (1, 10, 2, 1), (2, 11, 2, 2);
"""


class MissingRecordsMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.create_collation("RMNOCASE", rmutils.rmnocase)
        conn.executescript(SETUP_SQL)
        conn.commit()
        conn.close()
        self.out = self.tmp / "notes"

    def read(self, name: str) -> str:
        return (self.out / name).read_text(encoding="utf-8")

    def test_degree_0_lists_root_and_ancestors_only(self):
        code, out = self.run_main(missing_records.main, str(self.db), "--degree", "0", "--out", str(self.out))
        self.assertEqual(code, 0)
        self.assertIn("3 people (degrees 0-0), 1 with no Birth or Christen date", out)
        census = self.read("missing_censuses.md")
        self.assertIn("Generated 2026-01-02 from `test.rmtree`; root person P1 John smith; degrees 0-0.", census)
        self.assertNotIn("P1 John smith (1850-1910; root person): 1851 census", census)
        for year in (1861, 1871, 1881, 1891, 1901):
            self.assertIn(f"- [ ] P1 John smith (1850-1910; root person): {year} census (England; nearest place"
                          " Nottingham, Nottinghamshire, England, United Kingdom)", census)
        self.assertNotIn("1911 census (England", census.split("P2")[0])
        self.assertIn("P2 Dr Mary Brown (1820-; mother of P1): 1911 census", census)
        self.assertNotIn("P2 Dr Mary Brown (1820-; mother of P1): 1921 census", census)
        self.assertIn("- P3 Albert Brown, Jr (degree 0; father of P1)", census)
        self.assertNotIn("Peter", census)
        self.assertEqual(self.read("missing_birth_registers.md").count("- [ ]"), 0)
        deaths = self.read("missing_death_registers.md")
        self.assertIn("P1 John smith (1850-1910; root person): died 1910 (England;", deaths)
        self.assertIn("P2 Dr Mary Brown (1820-; mother of P1): Death not in tree: search 1837-1920 (age 100;", deaths)
        self.assertIn("P1 John smith (1850-1910; root person): F2 with P6 Ann Green, married 1875 (England;",
                      self.read("missing_marriage_registers.md"))

    def test_degree_1_adds_sibling_spouse_child_but_not_spouse_relatives(self):
        code, out = self.run_main(missing_records.main, str(self.db), "--degree", "1", "--out", str(self.out))
        self.assertEqual(code, 0)
        self.assertIn("6 people (degrees 0-1)", out)
        census = self.read("missing_censuses.md")
        self.assertIn("P5 Peter smith (1855-; sibling of P1): 1901 census (Ireland; nearest place Dublin, Ireland)",
                      census)
        self.assertNotIn("P5 Peter smith (1855-; sibling of P1): 1861 census", census)
        self.assertIn("P6 Ann Green (1852-; spouse of P1): 1861 census", census)
        self.assertNotIn("Sam", census)
        self.assertIn("P7 Tom smith (1930-; child of P1): 1939 Register", self.read("missing_1939_register.md"))
        deaths = self.read("missing_death_registers.md")
        self.assertIn("P5 Peter smith (1855-; sibling of P1): Death not in tree: search 1864-1955 (age 100; Ireland;",
                      deaths)
        self.assertNotIn("P7 Tom smith", deaths)
        births = self.read("missing_birth_registers.md")
        self.assertIn("P7 Tom smith (1930-; child of P1): born 1930 (England;", births)
        self.assertNotIn("P5 Peter smith", births)
        self.assertEqual(self.read("missing_marriage_registers.md").count("F2 with"), 1)


if __name__ == "__main__":
    unittest.main()
