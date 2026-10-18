import sqlite3
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

from support import FIXED_NOW, ScriptTestCase

import freebmd_deaths
from rmutils import read_fields

EXAMPLE_CONFIG = Path(__file__).resolve().parent.parent / "config.example.toml"
FOLDER = "H:\\My Drive\\Records\\Deaths\\Britain\\Registers"
FILE_DATES = {
    f"{FOLDER}\\smi-j-drb-1910-q2.jpg".lower(): date(2019, 2, 3),
    f"{FOLDER}\\bro-m-drb-1975-q4.jpg".lower(): date(2020, 9, 6),
}
TEMPLATE_6_FIELDS = [
    "DatabaseCreator", "DatabaseTitle", "Descriptor", "WebsiteCreator",
    "WebsiteTitle", "URL", "AccessDate", "SpecificItem", "Citing",
]


def old_fields(name: str) -> bytes:
    return (
        f"<Root><Fields><Field><Name>Name</Name><Value>{name}</Value></Field></Fields></Root>"
    ).encode("utf-8")


CITATIONS = [
    # CitationID, CitationName, ActualText
    (10, "smith John; ; April 1910–June 1910", "Deaths Jun 1910\r\nsmith \tJohn. \t60 \tMedway \t   2a \t383"),
    (11, "smith John; ; April 1910–June 1910", "Deaths Jun 1910\r\nsmith \tJohn. \t60 \tMedway \t   2a \t383"),
    (12, "BROWN MARY; ; 1975", "Deaths Dec 1975\r\nBROWN MARY 11 OC 1897 CHESTERFIELD    6 0259"),
    (13, "Brown Albert; ; 1850", "Deaths Mar 1850\r\nBrown \tAlbert \t\tS.Saviour \t IV \t427"),
    (14, "Brown Mary; ; 1988", "Deaths 1988\r\nBROWN \tMARY \t16 MR 1901 \tLEEDS \t   09.88 \t   6 \t0307"),
    (15, "Transcription missing", "Transcription missing"),
]
EVENTS = [
    # EventID, EventType, OwnerType, OwnerID
    (100, 1030, 0, 1),  # John Smith's Death Register event
    (101, 1, 0, 1),  # his Birth
    (102, 1030, 0, 2),
    (103, 1030, 0, 3),
    (104, 2, 0, 2),
]
LINKS = [
    # CitationID, OwnerType, OwnerID
    (10, 2, 100),
    (11, 2, 101),
    (12, 2, 102),
    (13, 2, 103),
    (14, 2, 104),
    (15, 2, 103),
]
MEDIA = [(1, FOLDER, "SMI-J-DRB-1910-Q2.jpg"), (2, FOLDER, "BRO-M-DRB-1975-Q4.jpg")]
MEDIA_LINKS = [(1, 4, 10), (1, 4, 11), (2, 4, 12)]  # MediaID, OwnerType, OwnerID

SETUP_SQL = """
CREATE TABLE SourceTemplateTable (TemplateID INTEGER PRIMARY KEY, Name TEXT, FieldDefs BLOB);
CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, Name TEXT, TemplateID INTEGER,
    Fields BLOB, UTCModDate FLOAT);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER,
    CitationName TEXT, ActualText TEXT, Fields BLOB, UTCModDate FLOAT);
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, EventType INTEGER,
    OwnerType INTEGER, OwnerID INTEGER);
CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER,
    OwnerType INTEGER, OwnerID INTEGER, UTCModDate FLOAT);
CREATE TABLE MultimediaTable (MediaID INTEGER PRIMARY KEY, MediaPath TEXT, MediaFile TEXT);
CREATE TABLE MediaLinkTable (LinkID INTEGER PRIMARY KEY, MediaID INTEGER,
    OwnerType INTEGER, OwnerID INTEGER, UTCModDate FLOAT);
"""


class FreeBmdDeathsMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        defs = "<Root><Fields>" + "".join(
            f"<Field><FieldName>{name}</FieldName></Field>" for name in TEMPLATE_6_FIELDS
        ) + "</Fields></Root>"
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.execute("INSERT INTO SourceTemplateTable VALUES (6, 'Complex Website', ?)",
                     (defs.encode("utf-8"),))
        conn.execute("INSERT INTO SourceTable VALUES (589, 'Death Register - UK - Freebmd', 10003, ?, 1.0)",
                     (old_fields("x"),))
        conn.executemany("INSERT INTO CitationTable VALUES (?, 589, ?, ?, ?, 1.0)",
                         [(cid, name, text, old_fields(name)) for cid, name, text in CITATIONS])
        conn.executemany("INSERT INTO EventTable VALUES (?, ?, ?, ?)", EVENTS)
        conn.executemany(
            "INSERT INTO CitationLinkTable (CitationID, OwnerType, OwnerID, UTCModDate) VALUES (?, ?, ?, 1.0)",
            LINKS)
        conn.executemany("INSERT INTO MultimediaTable VALUES (?, ?, ?)", MEDIA)
        conn.executemany(
            "INSERT INTO MediaLinkTable (MediaID, OwnerType, OwnerID, UTCModDate) VALUES (?, ?, ?, 1.0)",
            MEDIA_LINKS)
        conn.commit()
        conn.close()
        patcher = mock.patch.object(freebmd_deaths, "list_windows_file_dates", return_value=FILE_DATES)
        self.file_dates = patcher.start()
        self.addCleanup(patcher.stop)

    def run_script(self, *options: str) -> tuple[int, str]:
        return self.run_main(
            freebmd_deaths.main, str(self.db), "--config", str(EXAMPLE_CONFIG), *options
        )

    def remove_unconvertible(self) -> None:
        conn = sqlite3.connect(self.db)
        conn.execute("DELETE FROM CitationTable WHERE CitationID = 15")
        conn.execute("DELETE FROM CitationLinkTable WHERE CitationID = 15")
        conn.commit()
        conn.close()

    def report(self) -> str:
        return self.output_path("freebmd_deaths", "death_register").read_text(encoding="utf-8")

    def test_dry_run_lists_changes_and_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_script()

        self.assertEqual(code, 0)
        self.assertIn("6 citations; 4 to convert; 1 to merge; 1 cannot convert\nDry run: nothing changed.", out)
        self.assertEqual(self.db.read_bytes(), before)
        self.file_dates.assert_called_once_with("H:\\My Drive\\Records")
        text = self.report()
        for line in [
            "   name: 'Death Register - UK - Freebmd' -> 'Death Register - UK - FreeBMD'",
            "   template: 10003 -> 6 (Complex Website)",
            "   C15 'Transcription missing': transcription is not in FreeBMD's layout ('Deaths <quarter> <year>')",
            "   C11 -> C10 John smith [P1]",
            "   C13: no scan attached; access date left blank",
            "   AccessDate:   3 February 2019",
            "   SpecificItem: entry for John smith, age 60, Medway, vol. 2a, p. 383",
            "   Citing:       General Register Office, Deaths registered in April, May, and June 1910",
            "   text:         'Deaths Jun 1910\\r\\nsmith\\tJohn\\t60\\tMedway\\t2a\\t383'",
            "   SpecificItem: entry for Mary Brown, born 11 October 1897, Chesterfield, vol. 6, p. 0259",
            "   text:         'Deaths Dec 1975\\r\\nBROWN\\tMARY\\t11 OC 1897\\tCHESTERFIELD\\t6\\t0259'",
            "   SpecificItem: entry for Albert Brown, S.Saviour, vol. IV, p. 427",
            "   SpecificItem: entry for Mary Brown, born 16 March 1901, Leeds, registered September 1988, vol. 6, p. 0307",
            "   Citing:       General Register Office, Deaths registered in 1988",
        ]:
            self.assertIn(line + "\n", text)

    def test_apply_refused_while_a_citation_cannot_be_converted(self):
        before = self.db.read_bytes()
        code, out = self.run_script("--apply")

        self.assertEqual(code, 1)
        self.assertIn("Not applied", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply_writes_source_citations_and_merges_duplicates(self):
        self.remove_unconvertible()
        code, out = self.run_script("--apply")

        self.assertEqual(code, 0)
        self.assertIn("Applied: source S589, 4 citations updated, 1 merged.", out)
        stamp = (FIXED_NOW - datetime(1899, 12, 30)).total_seconds() / 86400
        conn = sqlite3.connect(self.db)
        name, template, fields, mod = conn.execute(
            "SELECT Name, TemplateID, Fields, UTCModDate FROM SourceTable WHERE SourceID = 589"
        ).fetchone()
        self.assertEqual((name, template), ("Death Register - UK - FreeBMD", 6))
        self.assertTrue(fields.startswith(b"<Root><Fields>"))
        self.assertEqual(read_fields(fields)["DatabaseTitle"], "England & Wales Civil Registration Death Index")
        self.assertAlmostEqual(mod, stamp)

        cname, fields, text = conn.execute(
            "SELECT CitationName, Fields, ActualText FROM CitationTable WHERE CitationID = 10"
        ).fetchone()
        item = "entry for John smith, age 60, Medway, vol. 2a, p. 383"
        citing = "General Register Office, Deaths registered in April, May, and June 1910"
        self.assertEqual(read_fields(fields), {"AccessDate": "3 February 2019", "SpecificItem": item,
                                               "Citing": citing})
        self.assertEqual(cname, f"3 February 2019; {item}; {citing}")
        self.assertEqual(text, "Deaths Jun 1910\r\nsmith\tJohn\t60\tMedway\t2a\t383")

        self.assertIsNone(conn.execute("SELECT 1 FROM CitationTable WHERE CitationID = 11").fetchone())
        self.assertEqual(
            sorted(conn.execute("SELECT OwnerID FROM CitationLinkTable WHERE CitationID = 10")),
            [(100,), (101,)])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM CitationLinkTable WHERE CitationID = 11").fetchone(),
                         (0,))
        self.assertEqual(conn.execute(
            "SELECT OwnerID FROM MediaLinkTable WHERE MediaID = 1").fetchall(), [(10,)])
        conn.close()

    def test_stops_if_template_fields_differ(self):
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE SourceTemplateTable SET FieldDefs = '<Root></Root>'")
        conn.commit()
        conn.close()

        code, out = self.run_script()
        self.assertEqual(code, 1)
        self.assertIn("Template 6 does not have the expected fields", out)

    def test_missing_source(self):
        code, out = self.run_script("--source", "999")
        self.assertEqual(code, 1)
        self.assertIn("Source S999 not found", out)

    def test_no_arguments_prints_usage(self):
        code, out = self.run_main(freebmd_deaths.main)
        self.assertEqual(code, 2)
        self.assertIn("Usage: python freebmd_deaths.py", out)


if __name__ == "__main__":
    unittest.main()
