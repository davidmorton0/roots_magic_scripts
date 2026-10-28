import sqlite3
import unittest
from datetime import date
from unittest import mock

from support import ScriptTestCase

import media
import rmutils

FOLDER = "H:\\My Drive\\Records\\Births\\Britain\\Registers"
SCAN = f"{FOLDER}\\DOE-J-BRG-1886-Q1.tif"
PDF = f"{FOLDER}\\DOE-J-BRG-1886-Q1.pdf"
THUMB = b"\xff\xd8thumbnail"
SETUP_SQL = """
CREATE TABLE MultimediaTable (MediaID INTEGER PRIMARY KEY, MediaType INTEGER, MediaPath TEXT,
    MediaFile TEXT, URL TEXT, Thumbnail BLOB, Caption TEXT, RefNumber TEXT, Date TEXT,
    SortDate BIGINT, Description TEXT, UTCModDate FLOAT);
CREATE TABLE MediaLinkTable (LinkID INTEGER PRIMARY KEY, MediaID INTEGER, OwnerType INTEGER,
    OwnerID INTEGER, IsPrimary INTEGER, Include1 INTEGER, Include2 INTEGER, Include3 INTEGER,
    Include4 INTEGER, SortOrder INTEGER, RectLeft INTEGER, RectTop INTEGER, RectRight INTEGER,
    RectBottom INTEGER, Comments TEXT, UTCModDate FLOAT);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY);
INSERT INTO CitationTable VALUES (10), (11);
INSERT INTO MultimediaTable VALUES (1, 1, 'H:\\My Drive\\Records\\Old', 'old.tif', '', NULL, 'Cap', '', '.',
    9223372036854775807, 'desc', 1.0);
INSERT INTO MediaLinkTable VALUES (1, 1, 4, 10, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, '', 1.0);
"""


class MediaMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.commit()
        conn.close()
        for name, value in (("windows_file_modified", date(2020, 1, 19)), ("windows_thumbnail", THUMB)):
            patcher = mock.patch.object(media, name, return_value=value)
            self.addCleanup(patcher.stop)
            setattr(self, name, patcher.start())

    def query(self, sql: str) -> list[tuple]:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute(sql).fetchall()
        finally:
            conn.close()

    def run_media(self, *args: str) -> tuple[int, str]:
        return self.run_main(media.main, str(self.db), *args)

    def test_get(self):
        code, out = self.run_media("get", "1")
        self.assertEqual(code, 0)
        self.assertIn("M1  H:\\My Drive\\Records\\Old\\old.tif", out)
        self.assertIn("link L1 -> citation 10 (IsPrimary 1)", out)
        self.assertIn("M1", self.run_media("get", "--owner", "citation:10")[1])
        self.assertIn("M1", self.run_media("get", "--file", "OLD")[1])
        self.assertIn("M1", self.run_media("get", "--path", "h:\\my drive\\records\\old\\OLD.TIF")[1])
        self.assertEqual(self.run_media("get", "--path", "H:\\My Drive\\Records\\Old\\other.tif")[0], 1)
        self.assertEqual(self.run_media("get", "--owner", "citation:11")[0], 1)
        self.assertEqual(self.run_media("get", "99")[0], 1)

    def test_create(self):
        before = self.db.read_bytes()
        args = ("create", "--path", SCAN, "--set", "Caption=Doe, Jane", "--set", "RefNumber=1886 Q1",
                "--date", "D.+18860315..+00000000..", "--link", "citation:11")
        self.assertEqual((self.run_media(*args)[0], self.db.read_bytes()), (0, before))
        code, out = self.run_media(*args, "--apply")
        self.assertEqual(code, 0)
        self.assertIn("Applied: media M2.", out)
        row = self.query("SELECT MediaType, MediaPath, MediaFile, URL, Thumbnail, Caption, RefNumber, Date, SortDate,"
                         " Description FROM MultimediaTable WHERE MediaID = 2")[0]
        self.assertEqual(row[:7], (1, FOLDER, "DOE-J-BRG-1886-Q1.tif", "", THUMB, "Doe, Jane", "1886 Q1"))
        self.assertEqual((row[7], row[9]), ("D.+18860315..+00000000..", ""))
        self.assertEqual(row[8], rmutils.sort_date("D.+18860315..+00000000.."))
        self.assertEqual(self.query("SELECT OwnerType, OwnerID, IsPrimary, Include1 FROM MediaLinkTable"
                                    " WHERE MediaID = 2"), [(4, 11, 1, 1)])

    def test_create_pdf_has_no_thumbnail_and_defaults(self):
        code, _ = self.run_media("create", "--path", PDF, "--link", "citation:10", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.query("SELECT MediaType, Thumbnail, Date, SortDate FROM MultimediaTable"
                                    " WHERE MediaID = 2"), [(2, None, ".", 9223372036854775807)])
        self.assertEqual(self.query("SELECT IsPrimary FROM MediaLinkTable WHERE MediaID = 2"), [(0,)])
        self.windows_thumbnail.assert_not_called()

    def test_create_refusals(self):
        self.windows_file_modified.return_value = None
        code, out = self.run_media("create", "--path", SCAN, "--set", "Bad=1", "--date", "D.+1886", "--link",
                                   "citation:99", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("file not found on disk", out)
        self.assertIn("--set 'Bad' is not one of", out)
        self.assertIn("SortDate not known", out)
        self.assertIn("citation 99 not found", out)
        self.windows_file_modified.return_value = date(2020, 1, 19)
        code, out = self.run_media("create", "--path", "H:\\My Drive\\Records\\OLD\\Old.TIF", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("M1 already uses", out)
        self.assertEqual(self.query("SELECT COUNT(*) FROM MultimediaTable"), [(1,)])

    def test_edit(self):
        code, out = self.run_media("edit", "1", "--set", "Caption=New", "--date", "D.+18860315..+00000000..",
                                   "--link", "citation:11", "--unlink", "citation:10", "--apply")
        self.assertEqual(code, 0)
        row = self.query("SELECT Caption, Date, SortDate, UTCModDate FROM MultimediaTable WHERE MediaID = 1")[0]
        self.assertEqual(row[:2], ("New", "D.+18860315..+00000000.."))
        self.assertLess(row[2], 9223372036854775807)
        self.assertGreater(row[3], 1.0)
        self.assertEqual(self.query("SELECT OwnerID, IsPrimary FROM MediaLinkTable WHERE MediaID = 1"), [(11, 1)])

    def test_edit_path_and_refusals(self):
        code, _ = self.run_media("edit", "1", "--path", SCAN, "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.query("SELECT MediaPath, MediaFile FROM MultimediaTable"),
                         [(FOLDER, "DOE-J-BRG-1886-Q1.tif")])
        code, out = self.run_media("edit", "1", "--link", "citation:10", "--unlink", "citation:11", "--link",
                                   "citation:99")
        self.assertEqual(code, 1)
        self.assertIn("M1 is already linked to citation 10", out)
        self.assertIn("M1 is not linked to citation 11", out)
        self.assertIn("citation 99 not found", out)
        self.assertEqual(self.run_media("edit", "99", "--set", "Caption=x")[0], 1)
        self.assertEqual(self.run_media("edit", "1")[0], 1)

    def test_delete(self):
        code, out = self.run_media("delete", "1", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("1 links; give --with-links", out)
        before = self.db.read_bytes()
        self.assertEqual((self.run_media("delete", "1", "--with-links")[0], self.db.read_bytes()), (0, before))
        code, _ = self.run_media("delete", "1", "--with-links", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.query("SELECT COUNT(*) FROM MultimediaTable"), [(0,)])
        self.assertEqual(self.query("SELECT COUNT(*) FROM MediaLinkTable"), [(0,)])


if __name__ == "__main__":
    unittest.main()
