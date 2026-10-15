import sqlite3
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

from support import FIXED_NOW, ScriptTestCase

import freebmd_births
from rmutils import read_fields

EXAMPLE_CONFIG = Path(__file__).resolve().parent.parent / "config.example.toml"
FOLDER = "H:\\My Drive\\Records\\Births\\Britain\\Registers"
FILE_DATES = {
    f"{FOLDER}\\doe-j-brg-1886-q1.tif".lower(): date(2019, 2, 3),
    f"{FOLDER}\\poe-a-brg-1934-q4.jpg".lower(): date(2020, 9, 6),
}

TEMPLATE_6_FIELDS = [
    "DatabaseCreator", "DatabaseTitle", "Descriptor", "WebsiteCreator",
    "WebsiteTitle", "URL", "AccessDate", "SpecificItem", "Citing",
]
OLD_SOURCE_FIELDS = (
    '\ufeff<?xml version="1.0" encoding="UTF-8"?>\n<Root><Fields>'
    "<Field><Name>Repository</Name><Value>GRO</Value></Field></Fields></Root>\n"
).encode("utf-8")


def old_citation_fields(name: str, cert: str, when: str) -> bytes:
    return (
        "<Root><Fields>"
        f"<Field><Name>Name</Name><Value>{name}</Value></Field>"
        "<Field><Name>Form</Name><Value></Value></Field>"
        f"<Field><Name>CertificateNo</Name><Value>{cert}</Value></Field>"
        f"<Field><Name>Date</Name><Value>{when}</Value></Field>"
        "</Fields></Root>"
    ).encode("utf-8")


ANCESTRY_TEXT = (
    "Name: \tAnn Poe\r\nRegistration Date: \tOct 1934\r\n[Nov 1934] \r\n"
    "Registration Quarter: \tOct-Nov-Dec\r\nRegistration District: \tBasford\r\n"
    "Mother's Maiden Name: \tFenwick\r\nVolume Number: \t7b\r\nPage Number: \t252\r\n"
    "Source Citation\r\n\r\nGeneral Register Office; United Kingdom"
)

CITATIONS = [
    # CitationID, CitationName, ActualText, Comments, Fields
    (
        10,
        "Jane Doe; ; ; January 1886–March 1886",
        "Births Mar 1886\r\nDoe \tJane \tMedway \t   2a \t602\r\nhttps://www.freebmd.org.uk/cgi/x",
        "",
        old_citation_fields("Jane Doe", "", "January 1886–March 1886"),
    ),
    (
        11,
        "Tom Roe; ; ; July 1960–September 1960",
        "Births Sep 1960   (>99%)\r\nROE \tTOM \tSMITH \tLEEDS \t   2c \t533",
        "1 of 2 possible records",
        old_citation_fields("Tom Roe", "", "July 1960–September 1960"),
    ),
    (
        12,
        "Roe \tAnn; ; Basford \t XV \t458; January 1844–March 1844",
        "",
        "",
        old_citation_fields("Roe \tAnn", "Basford \t XV \t458", "January 1844–March 1844"),
    ),
    (
        13,
        "Ann Poe; ; ; Volume 7b, Page 252",
        ANCESTRY_TEXT,
        "",
        old_citation_fields("Ann Poe", "", "Volume 7b, Page 252"),
    ),
    (
        14,
        "Notes only",
        "some notes about a search",
        "",
        old_citation_fields("", "", ""),
    ),
]
MEDIA = [
    # MediaID, MediaPath, MediaFile
    (1, FOLDER, "DOE-J-BRG-1886-Q1.tif"),
    (2, FOLDER, "ROE-T-BRG-1960-Q3.jpg"),
    (3, FOLDER, "POE-A-BRG-1934-Q4.jpg"),
]
MEDIA_LINKS = [(1, 4, 10), (2, 4, 11), (3, 4, 13)]  # MediaID, OwnerType, OwnerID

SETUP_SQL = """
CREATE TABLE SourceTemplateTable (TemplateID INTEGER PRIMARY KEY, Name TEXT, FieldDefs BLOB);
CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, Name TEXT, TemplateID INTEGER,
    Fields BLOB, UTCModDate FLOAT);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER,
    CitationName TEXT, ActualText TEXT, Comments TEXT, Fields BLOB, UTCModDate FLOAT);
CREATE TABLE MultimediaTable (MediaID INTEGER PRIMARY KEY, MediaPath TEXT, MediaFile TEXT);
CREATE TABLE MediaLinkTable (LinkID INTEGER PRIMARY KEY, MediaID INTEGER,
    OwnerType INTEGER, OwnerID INTEGER);
"""


class FreeBmdBirthsMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        defs = "<Root><Fields>" + "".join(
            f"<Field><FieldName>{name}</FieldName></Field>" for name in TEMPLATE_6_FIELDS
        ) + "</Fields></Root>"
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.execute(
            "INSERT INTO SourceTemplateTable VALUES (6, 'Complex Website', ?)",
            (defs.encode("utf-8"),),
        )
        conn.execute(
            "INSERT INTO SourceTable VALUES (583, 'Birth Register UK', 10001, ?, 1.0)",
            (OLD_SOURCE_FIELDS,),
        )
        conn.executemany("INSERT INTO CitationTable VALUES (?, 583, ?, ?, ?, ?, 1.0)", CITATIONS)
        conn.executemany("INSERT INTO MultimediaTable VALUES (?, ?, ?)", MEDIA)
        conn.executemany(
            "INSERT INTO MediaLinkTable (MediaID, OwnerType, OwnerID) VALUES (?, ?, ?)",
            MEDIA_LINKS,
        )
        conn.commit()
        conn.close()
        patcher = mock.patch.object(
            freebmd_births, "list_windows_file_dates", return_value=FILE_DATES
        )
        self.file_dates = patcher.start()
        self.addCleanup(patcher.stop)

    def run_script(self, *options: str) -> tuple[int, str]:
        return self.run_main(
            freebmd_births.main, str(self.db), "--config", str(EXAMPLE_CONFIG), *options
        )

    def remove_unconvertible(self) -> None:
        conn = sqlite3.connect(self.db)
        conn.execute("DELETE FROM CitationTable WHERE CitationID = 14")
        conn.commit()
        conn.close()

    def test_dry_run_lists_changes_and_issues_and_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_script()

        self.assertEqual(code, 0)
        self.assertIn("5 citations; 4 to convert; 1 cannot convert\nDry run: nothing changed.", out)
        self.assertEqual(self.db.read_bytes(), before)
        self.file_dates.assert_called_once_with("H:\\My Drive\\Records")
        text = self.output_path("freebmd_births", "birth_register").read_text(encoding="utf-8")
        for line in [
            "   template: 10001 -> 6 (Complex Website)",
            "   C14 'Notes only': transcription is in neither FreeBMD's nor Ancestry's layout",
            f"   C11: scan not found on disk: {FOLDER}\\ROE-T-BRG-1960-Q3.jpg",
            "   C11: citation note: '1 of 2 possible records'",
            "   C12: no transcription; built from the old Name and Certificate number fields",
            "   C12: no scan attached; access date left blank",
            "   C13: transcription is from Ancestry, not FreeBMD; belongs under an Ancestry source",
            "   AccessDate:   3 February 2019",
            "   SpecificItem: entry for Jane Doe, Medway, vol. 2a, p. 602",
            "   Citing:       General Register Office, Births registered in January, February, and March 1886",
            "   SpecificItem: entry for Tom Roe, Leeds, vol. 2c, p. 533, mother's maiden name Smith",
            "   SpecificItem: entry for Ann Roe, Basford, vol. XV, p. 458",
            "   SpecificItem: entry for Ann Poe, Basford, vol. 7b, p. 252, mother's maiden name Fenwick",
            "   Citing:       General Register Office, Births registered in October, November, and December 1934",
        ]:
            self.assertIn(line + "\n", text)

    def test_apply_refused_while_a_citation_cannot_be_converted(self):
        before = self.db.read_bytes()
        code, out = self.run_script("--apply")

        self.assertEqual(code, 1)
        self.assertIn("Not applied", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply_writes_source_and_citations(self):
        self.remove_unconvertible()
        code, out = self.run_script("--apply")

        self.assertEqual(code, 0)
        self.assertIn("Applied: source S583 and 4 citations updated.", out)
        stamp = (FIXED_NOW - datetime(1899, 12, 30)).total_seconds() / 86400
        conn = sqlite3.connect(self.db)
        template, fields, mod = conn.execute(
            "SELECT TemplateID, Fields, UTCModDate FROM SourceTable WHERE SourceID = 583"
        ).fetchone()
        self.assertEqual(template, 6)
        self.assertTrue(fields.startswith('\ufeff<?xml version="1.0"'.encode("utf-8")))
        self.assertEqual(read_fields(fields)["WebsiteTitle"], "FreeBMD")
        self.assertAlmostEqual(mod, stamp)

        name, fields, mod = conn.execute(
            "SELECT CitationName, Fields, UTCModDate FROM CitationTable WHERE CitationID = 10"
        ).fetchone()
        poe = read_fields(conn.execute(
            "SELECT Fields FROM CitationTable WHERE CitationID = 13"
        ).fetchone()[0])
        conn.close()
        expected_item = "entry for Jane Doe, Medway, vol. 2a, p. 602"
        expected_citing = (
            "General Register Office, Births registered in January, February, and March 1886"
        )
        self.assertEqual(
            read_fields(fields),
            {"AccessDate": "3 February 2019", "SpecificItem": expected_item, "Citing": expected_citing},
        )
        self.assertTrue(fields.startswith(b"<Root><Fields>"))
        self.assertEqual(name, f"3 February 2019; {expected_item}; {expected_citing}")
        self.assertAlmostEqual(mod, stamp)
        self.assertEqual(poe["AccessDate"], "6 September 2020")

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
        code, out = self.run_main(freebmd_births.main)
        self.assertEqual(code, 2)
        self.assertIn("Usage: python freebmd_births.py", out)


if __name__ == "__main__":
    unittest.main()
