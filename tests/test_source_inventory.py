import sqlite3
import unittest

from support import ScriptTestCase

import rmutils
import source_inventory

SETUP_SQL = """
CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, Name TEXT, TemplateID INTEGER, Fields BLOB,
    ActualText TEXT, Comments TEXT);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER, CitationName TEXT, Fields BLOB,
    ActualText TEXT, Comments TEXT);
CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER, OwnerType INTEGER,
    OwnerID INTEGER, Quality TEXT);
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, EventType INTEGER, OwnerType INTEGER, OwnerID INTEGER,
    Date TEXT, PlaceID INTEGER, SiteID INTEGER, Details TEXT);
CREATE TABLE FactTypeTable (FactTypeID INTEGER PRIMARY KEY, Name TEXT);
CREATE TABLE FamilyTable (FamilyID INTEGER PRIMARY KEY, FatherID INTEGER, MotherID INTEGER);
CREATE TABLE PlaceTable (PlaceID INTEGER PRIMARY KEY, Name TEXT);
CREATE TABLE MultimediaTable (MediaID INTEGER PRIMARY KEY, MediaPath TEXT, MediaFile TEXT);
CREATE TABLE MediaLinkTable (LinkID INTEGER PRIMARY KEY, MediaID INTEGER, OwnerType INTEGER, OwnerID INTEGER);
INSERT INTO FactTypeTable VALUES (1, 'Birth'), (300, 'Marriage');
INSERT INTO FamilyTable VALUES (5, 3, 2);
INSERT INTO PlaceTable VALUES (10, 'Testham, Exampleshire, England'), (11, 'St Peter');
INSERT INTO EventTable VALUES
    (20, 300, 1, 5, 'D.+18800101..+00000000..', 10, 11, ''),
    (21, 1, 0, 1, 'D.+18500000..+00000000..', 10, 0, 'twin');
INSERT INTO MultimediaTable VALUES (40, 'C:\\Scans', 'BRO.A-MCIB-1880.jpg');
INSERT INTO MediaLinkTable VALUES (1, 40, 4, 30);
"""


class SourceInventoryMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.execute("INSERT INTO SourceTable VALUES (7, 'Marriages - Test', 6, ?, 'About it', '')",
                     (rmutils.fields_blob({"DatabaseTitle": "Test Marriages"}, declaration=False),))
        conn.executemany(
            "INSERT INTO CitationTable VALUES (?, 7, ?, ?, ?, ?)",
            [(30, "entry 1", rmutils.fields_blob({"SpecificItem": "entry 1"}, declaration=False), "Name: Albert",
              "see task"),
             (31, "entry 2", rmutils.fields_blob({"SpecificItem": "entry 2"}, declaration=False), "", "")])
        conn.executemany("INSERT INTO CitationLinkTable (CitationID, OwnerType, OwnerID, Quality) VALUES (?, ?, ?, ?)",
                         [(30, 2, 20, "PDO"), (30, 1, 5, "PDO"), (31, 2, 21, "SIX"), (31, 2, 99, "~~~")])
        conn.commit()
        conn.close()

    def test_lists_source_citations_links_and_scans(self):
        before = self.db.read_bytes()
        code, out = self.run_main(source_inventory.main, str(self.db), "7")
        self.assertEqual(code, 0)
        self.assertIn("S7: 2 citations", out)
        self.assertEqual(self.db.read_bytes(), before)
        text = self.output_path("source_7_inventory").read_text(encoding="utf-8")
        self.assertIn("S7 Marriages - Test, template 6", text)
        self.assertIn("{'DatabaseTitle': 'Test Marriages'}", text)
        self.assertIn("note: 'see task'", text)
        self.assertIn("link E20 Marriage F5 (3, 2) D.+18800101..+00000000.. Testham, Exampleshire, England"
                      " / St Peter [PDO]", text)
        self.assertIn("link owner type 1, ID 5 [PDO]", text)
        self.assertIn("link E21 Birth P1 John smith D.+18500000..+00000000.. Testham, Exampleshire, England"
                      " / - 'twin' [SIX]", text)
        self.assertIn("link E99 (missing event) [~~~]", text)
        self.assertIn("scan M40 C:\\Scans\\BRO.A-MCIB-1880.jpg", text)
        self.assertIn("event links by fact: {'Birth': 1, 'Marriage': 1}", text)

    def test_unknown_source(self):
        code, out = self.run_main(source_inventory.main, str(self.db), "8")
        self.assertEqual(code, 1)
        self.assertIn("No source S8", out)


if __name__ == "__main__":
    unittest.main()
