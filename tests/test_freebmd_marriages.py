import sqlite3
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from support import ScriptTestCase

import freebmd_marriages
from rmutils import read_fields

EXAMPLE_CONFIG = Path(__file__).resolve().parent.parent / "config.example.toml"
FOLDER = "H:\\My Drive\\Records\\Marriage - Civil Registration\\Britain\\Register Images"
TEMPLATE_6_FIELDS = ["DatabaseCreator", "DatabaseTitle", "Descriptor", "WebsiteCreator", "WebsiteTitle",
                     "URL", "AccessDate", "SpecificItem", "Citing"]
TEXT = ("Marriages Sep 1885   (>99%)\r\nSMITH\t John\t \t Medway\t 2a\t867\r\nBrown\t Mary\t  \t Medway\t 2a\t867\r\n"
        "COGGIN\t Annie\t  \t Medway\t 2a\t867")

SETUP_SQL = """
CREATE TABLE SourceTemplateTable (TemplateID INTEGER PRIMARY KEY, Name TEXT, FieldDefs BLOB);
CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, Name TEXT, TemplateID INTEGER, Fields BLOB,
    ActualText TEXT, Comments TEXT, UTCModDate FLOAT);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER, Comments TEXT, ActualText TEXT,
    RefNumber TEXT, Footnote TEXT, ShortFootnote TEXT, Bibliography TEXT, Fields BLOB, UTCModDate FLOAT,
    CitationName TEXT);
CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER, OwnerType INTEGER,
    OwnerID INTEGER, SortOrder INTEGER, Quality TEXT, IsPrivate INTEGER, Flags INTEGER, UTCModDate FLOAT);
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, EventType INTEGER, OwnerType INTEGER, OwnerID INTEGER,
    FamilyID INTEGER, PlaceID INTEGER, SiteID INTEGER, Date TEXT, SortDate BIGINT, IsPrimary INTEGER,
    IsPrivate INTEGER, Proof INTEGER, Status INTEGER, Sentence TEXT, Details TEXT, Note TEXT, UTCModDate FLOAT);
CREATE TABLE FamilyTable (FamilyID INTEGER PRIMARY KEY, FatherID INTEGER, MotherID INTEGER);
CREATE TABLE MultimediaTable (MediaID INTEGER PRIMARY KEY, MediaType INTEGER, MediaPath TEXT, MediaFile TEXT,
    URL TEXT, Thumbnail BLOB, Caption TEXT, RefNumber TEXT, Date TEXT, SortDate BIGINT, Description TEXT,
    UTCModDate FLOAT);
CREATE TABLE MediaLinkTable (LinkID INTEGER PRIMARY KEY, MediaID INTEGER, OwnerType INTEGER, OwnerID INTEGER,
    IsPrimary INTEGER, Include1 INTEGER, Include2 INTEGER, Include3 INTEGER, Include4 INTEGER, SortOrder INTEGER,
    RectLeft INTEGER, RectTop INTEGER, RectRight INTEGER, RectBottom INTEGER, Comments TEXT, UTCModDate FLOAT);
CREATE TABLE TaskLinkTable (LinkID INTEGER PRIMARY KEY, OwnerType INTEGER, OwnerID INTEGER);
CREATE TABLE URLTable (LinkID INTEGER PRIMARY KEY, OwnerType INTEGER, OwnerID INTEGER);
CREATE TABLE WitnessTable (WitnessID INTEGER PRIMARY KEY, EventID INTEGER);
INSERT INTO SourceTable VALUES (587, 'Marriage Register - UK', 10009, NULL, 'www.freebmd.org.uk', '', 1.0);
INSERT INTO FamilyTable VALUES (5, 1, 2);
-- register events for both partners (person 1 John Smith, person 2 Mary Brown); the family has no Marriage
INSERT INTO EventTable (EventID, EventType, OwnerType, OwnerID, PlaceID, SiteID, Date) VALUES
    (10, 1028, 0, 1, 7, 0, 'D-+18850700.A+18850900..'), (11, 1028, 0, 2, 7, 0, 'D-+18850700.A+18850900..');
INSERT INTO CitationLinkTable (CitationID, OwnerType, OwnerID, Quality) VALUES (20, 2, 10, '~~~'), (21, 2, 11, '~~~');
INSERT INTO MultimediaTable (MediaID, MediaType, MediaPath, MediaFile, Caption) VALUES
    (30, 1, 'H:\\My Drive\\Records\\Marriage - Civil Registration\\Britain\\Register Images', 'SMI.J-MRB-1885-Q3.jpg', ''),
    (31, 1, 'H:\\My Drive\\Records\\Marriage - Civil Registration\\Britain\\Register Images', 'BRO.M-MRB-1885-Q3.jpg', '');
INSERT INTO MediaLinkTable (MediaID, OwnerType, OwnerID) VALUES (30, 4, 20), (31, 4, 20), (30, 4, 21), (31, 4, 21);
"""


class FreeBmdMarriagesMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        defs = "<Root><Fields>" + "".join(
            f"<Field><FieldName>{n}</FieldName></Field>" for n in TEMPLATE_6_FIELDS) + "</Fields></Root>"
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.execute("INSERT INTO SourceTemplateTable VALUES (6, 'Complex Website', ?)", (defs.encode(),))
        conn.executemany("INSERT INTO CitationTable (CitationID, SourceID, ActualText, Fields) VALUES (?, 587, ?, NULL)",
                         [(20, TEXT), (21, TEXT)])
        # people 1 (smith, John) and 2 (Brown, Mary) come from the shared fixture
        conn.commit()
        conn.close()
        patcher = mock.patch.object(freebmd_marriages, "list_windows_file_dates", return_value={
            f"{FOLDER}\\smi.j-mrb-1885-q3.jpg".lower(): date(2019, 2, 3),
            f"{FOLDER}\\bro.m-mrb-1885-q3.jpg".lower(): date(2019, 2, 4)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_script(self, *options):
        return self.run_main(freebmd_marriages.main, str(self.db), "--config", str(EXAMPLE_CONFIG), *options)

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_script()
        self.assertEqual(code, 0)
        self.assertIn("1 families; 1 to rework; 0 left unchanged; 0 citations not linked to a family", out)
        self.assertEqual(self.db.read_bytes(), before)
        text = self.output_path("freebmd_marriages", "marriage_register").read_text(encoding="utf-8")
        self.assertIn("      SpecificItem: entry for John Smith, Medway, vol. 2a, p. 867\n", text)

    def test_apply_splits_per_partner_on_the_marriage(self):
        code, out = self.run_script("--apply")
        self.assertEqual(code, 0)
        self.assertIn("1 families reworked; 2 register events deleted", out)
        conn = sqlite3.connect(self.db)
        name, template, text = conn.execute("SELECT Name, TemplateID, ActualText FROM SourceTable").fetchone()
        self.assertEqual((name, template), ("Marriage Register - UK - FreeBMD", 6))
        marriage = conn.execute("SELECT EventID, OwnerType, OwnerID, Date, PlaceID FROM EventTable"
                                " WHERE EventType = 300").fetchone()
        self.assertEqual(marriage[1:], (1, 5, "DB+18851000..+00000000..", 7))
        self.assertIsNone(conn.execute("SELECT 1 FROM EventTable WHERE EventType = 1028").fetchone())
        rows = conn.execute("SELECT c.CitationID, c.ActualText, c.Fields, l.OwnerID, l.Quality, m.MediaID"
                            " FROM CitationTable c JOIN CitationLinkTable l USING (CitationID)"
                            " JOIN MediaLinkTable m ON m.OwnerType = 4 AND m.OwnerID = c.CitationID"
                            " ORDER BY c.CitationID").fetchall()
        caption = conn.execute("SELECT Caption, RefNumber FROM MultimediaTable WHERE MediaID = 31").fetchone()
        conn.close()
        self.assertEqual([(r[0], r[3], r[4], r[5]) for r in rows],
                         [(20, marriage[0], "PIX", 30), (21, marriage[0], "PIX", 31)])
        self.assertEqual(rows[0][1], "Marriages Sep 1885\r\nSMITH\tJohn\t\tMedway\t2a\t867\r\n"
                                     "Also on the page: Brown Mary; COGGIN Annie")
        self.assertEqual(read_fields(rows[1][2]), {
            "AccessDate": "4 February 2019",
            "SpecificItem": "entry for Mary Brown, Medway, vol. 2a, p. 867",
            "Citing": "General Register Office, Marriages registered in July, August, and September 1885"})
        self.assertEqual(caption, ("Brown, Mary – marriage index – 1885 Q3", "1885 Q3 Medway 2a 867"))

    def test_no_arguments_prints_usage(self):
        code, out = self.run_main(freebmd_marriages.main)
        self.assertEqual(code, 2)
        self.assertIn("Usage: python freebmd_marriages.py", out)


if __name__ == "__main__":
    unittest.main()
