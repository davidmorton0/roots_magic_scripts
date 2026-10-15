import sqlite3
import unittest
from datetime import date, datetime
from unittest import mock

from support import FIXED_NOW, ScriptTestCase

import attach_scan
from rmutils import read_fields

FOLDER = "H:\\My Drive\\Records\\Births\\Britain\\Registers"
SCAN = f"{FOLDER}\\DOE-J-BRG-1886-Q1.tif"
THUMB = b"\xff\xd8thumbnail"
FIELD_DEFS = (
    "<Root><Fields>"
    "<Field><FieldName>WebsiteTitle</FieldName><CitationField>False</CitationField></Field>"
    "<Field><FieldName>AccessDate</FieldName><CitationField>True</CitationField></Field>"
    "<Field><FieldName>SpecificItem</FieldName><CitationField>True</CitationField></Field>"
    "</Fields></Root>"
)
CITATION_FIELDS = (
    "<Root><Fields>"
    "<Field><Name>AccessDate</Name><Value></Value></Field>"
    "<Field><Name>SpecificItem</Name><Value>entry for Jane Doe</Value></Field>"
    "</Fields></Root>"
)

SETUP_SQL = """
CREATE TABLE SourceTemplateTable (TemplateID INTEGER PRIMARY KEY, Name TEXT, FieldDefs BLOB);
CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, Name TEXT, TemplateID INTEGER);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER,
    CitationName TEXT, Fields BLOB, UTCModDate FLOAT);
CREATE TABLE MultimediaTable (MediaID INTEGER PRIMARY KEY, MediaType INTEGER, MediaPath TEXT,
    MediaFile TEXT, URL TEXT, Thumbnail BLOB, Caption TEXT, RefNumber TEXT, Date TEXT,
    SortDate BIGINT, Description TEXT, UTCModDate FLOAT);
CREATE TABLE MediaLinkTable (LinkID INTEGER PRIMARY KEY, MediaID INTEGER, OwnerType INTEGER,
    OwnerID INTEGER, IsPrimary INTEGER, Include1 INTEGER, Include2 INTEGER, Include3 INTEGER,
    Include4 INTEGER, SortOrder INTEGER, RectLeft INTEGER, RectTop INTEGER, RectRight INTEGER,
    RectBottom INTEGER, Comments TEXT, UTCModDate FLOAT);
"""


class AttachScanMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.execute("INSERT INTO SourceTemplateTable VALUES (6, 'Complex Website', ?)",
                     (FIELD_DEFS.encode("utf-8"),))
        conn.execute("INSERT INTO SourceTable VALUES (583, 'Birth index', 6)")
        conn.execute(
            "INSERT INTO CitationTable VALUES (10, 583, '; entry for Jane Doe', ?, 1.0)",
            (CITATION_FIELDS.encode("utf-8"),),
        )
        conn.commit()
        conn.close()
        for name, value in (
            ("windows_file_modified", date(2020, 1, 19)),
            ("windows_thumbnail", THUMB),
        ):
            patcher = mock.patch.object(attach_scan, name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def query(self, sql: str):
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute(sql).fetchall()
        finally:
            conn.close()

    def test_dry_run_shows_changes_and_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(attach_scan.main, str(self.db), "10", SCAN)

        self.assertEqual(code, 0)
        self.assertEqual(self.db.read_bytes(), before)
        self.assertIn(f"   add media: {SCAN}\n", out)
        self.assertIn("      MediaType 1; Date '.'; thumbnail 11 bytes\n", out)
        self.assertIn("   link media -> citation C10 (OwnerType 4); IsPrimary 1; Include1 1\n", out)
        self.assertIn("   AccessDate: '' -> '19 January 2020' (file last modified 2020-01-19)\n", out)
        self.assertIn("Dry run: nothing changed.", out)

    def test_apply_adds_media_link_and_access_date(self):
        code, out = self.run_main(attach_scan.main, str(self.db), "10", SCAN, "--apply")

        self.assertEqual(code, 0)
        self.assertIn("Applied: media M1 attached to citation C10.", out)
        stamp = (FIXED_NOW - datetime(1899, 12, 30)).total_seconds() / 86400
        media = self.query(
            "SELECT MediaType, MediaPath, MediaFile, URL, Thumbnail, Caption, RefNumber, Date,"
            " SortDate, Description, UTCModDate FROM MultimediaTable"
        )
        self.assertEqual(len(media), 1)
        self.assertEqual(
            media[0][:10],
            (1, FOLDER, "DOE-J-BRG-1886-Q1.tif", "", THUMB, "", "", ".", 9223372036854775807, ""),
        )
        self.assertAlmostEqual(media[0][10], stamp)
        self.assertEqual(
            self.query(
                "SELECT MediaID, OwnerType, OwnerID, IsPrimary, Include1, Include2, Include3,"
                " Include4, SortOrder, RectLeft, RectTop, RectRight, RectBottom, Comments"
                " FROM MediaLinkTable"
            ),
            [(1, 4, 10, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, "")],
        )
        name, fields = self.query("SELECT CitationName, Fields FROM CitationTable")[0]
        self.assertEqual(name, "19 January 2020; entry for Jane Doe")
        self.assertEqual(
            read_fields(fields),
            {"AccessDate": "19 January 2020", "SpecificItem": "entry for Jane Doe"},
        )

    def test_reuses_existing_media_row_and_keeps_existing_access_date(self):
        conn = sqlite3.connect(self.db)
        conn.execute(
            "INSERT INTO MultimediaTable (MediaID, MediaType, MediaPath, MediaFile)"
            " VALUES (7, 1, ?, 'doe-j-brg-1886-q1.tif')",
            (FOLDER.lower(),),
        )
        conn.execute(
            "UPDATE CitationTable SET Fields = replace(Fields, '<Value></Value>',"
            " '<Value>1 May 2019</Value>')"
        )
        conn.execute(
            "INSERT INTO MediaLinkTable (MediaID, OwnerType, OwnerID) VALUES (7, 4, 99)"
        )
        conn.commit()
        conn.close()

        code, out = self.run_main(attach_scan.main, str(self.db), "10", SCAN, "--apply")

        self.assertEqual(code, 0)
        self.assertIn("   reuse media M7:", out)
        self.assertIn("   AccessDate: unchanged", out)
        self.assertEqual(self.query("SELECT COUNT(*) FROM MultimediaTable"), [(1,)])
        self.assertEqual(
            self.query("SELECT MediaID, OwnerID FROM MediaLinkTable ORDER BY LinkID"),
            [(7, 99), (7, 10)],
        )

    def test_refuses_if_already_attached(self):
        self.run_main(attach_scan.main, str(self.db), "10", SCAN, "--apply")
        code, out = self.run_main(attach_scan.main, str(self.db), "10", SCAN, "--apply")

        self.assertEqual(code, 1)
        self.assertIn("is already attached to citation C10", out)
        self.assertEqual(self.query("SELECT COUNT(*) FROM MediaLinkTable"), [(1,)])

    def test_refuses_if_file_not_on_disk(self):
        attach_scan.windows_file_modified.return_value = None
        before = self.db.read_bytes()
        code, out = self.run_main(attach_scan.main, str(self.db), "10", SCAN, "--apply")

        self.assertEqual(code, 1)
        self.assertIn(f"File not found on disk: {SCAN}", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_missing_citation(self):
        code, out = self.run_main(attach_scan.main, str(self.db), "999", SCAN)
        self.assertEqual(code, 1)
        self.assertIn("Citation C999 not found", out)

    def test_no_arguments_prints_usage(self):
        code, out = self.run_main(attach_scan.main)
        self.assertEqual(code, 2)
        self.assertIn("Usage: python attach_scan.py", out)


if __name__ == "__main__":
    unittest.main()
