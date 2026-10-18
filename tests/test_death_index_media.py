import sqlite3
import unittest

from support import ScriptTestCase

import death_index_media
from rmutils import sort_date

FOLDER = "H:\\My Drive\\Records\\Deaths\\Britain\\Registers"


def fields(item: str, citing: str) -> bytes:
    return (
        "<Root><Fields>"
        f"<Field><Name>SpecificItem</Name><Value>{item}</Value></Field>"
        f"<Field><Name>Citing</Name><Value>{citing}</Value></Field>"
        "</Fields></Root>"
    ).encode("utf-8")


Q2_1910 = "General Register Office, Deaths registered in April, May, and June 1910"
CITATIONS = [
    # CitationID, Fields, ActualText
    (10, fields("entry for John Smith, age 60, Medway, vol. 2a, p. 383", Q2_1910),
     "Deaths Jun 1910\r\nSMITH\tJOHN\t60\tMedway\t2a\t383"),
    (11, fields("entry for Mary Brown, born 16 March 1901, Leeds, registered September 1988,"
                " vol. 6, p. 0307", "General Register Office, Deaths registered in 1988"),
     "Deaths 1988\r\nBROWN\tMARY\t16 MR 1901\tLEEDS\t09.88\t6\t0307"),
    (12, fields("entry for Ann Roe, age 5, Medway, vol. 2a, p. 380", Q2_1910),
     "Deaths Jun 1910\r\nRoe\tAnn\t5\tMedway\t2a\t380"),
    (13, fields("entry for Tom Roe, age 7, Medway, vol. 2a, p. 381", Q2_1910),
     "Deaths Jun 1910\r\nRoe\tTom\t7\tMedway\t2a\t381"),
]
MEDIA = [
    # MediaID, MediaFile, Caption
    (1, "SMI-J-DRB-1910-Q2.jpg", ""),
    (2, "BRO-M-DRB-1988.jpg", "Already set"),
    (3, "ROE-A-DRB-1910-Q2.jpg", ""),  # shared by two different entries
]
MEDIA_LINKS = [(1, 10), (2, 11), (3, 12), (3, 13)]

SETUP_SQL = """
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, Date TEXT, SortDate BIGINT);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER, Fields BLOB,
    ActualText TEXT);
CREATE TABLE MultimediaTable (MediaID INTEGER PRIMARY KEY, MediaPath TEXT, MediaFile TEXT,
    Caption TEXT, RefNumber TEXT, Description TEXT, Date TEXT, SortDate BIGINT, UTCModDate FLOAT,
    MediaType INTEGER DEFAULT 1, URL TEXT DEFAULT '', Thumbnail BLOB DEFAULT x'0102');
CREATE TABLE MediaLinkTable (LinkID INTEGER PRIMARY KEY, MediaID INTEGER,
    OwnerType INTEGER, OwnerID INTEGER, UTCModDate FLOAT);
"""


class DeathIndexMediaMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.executemany("INSERT INTO CitationTable VALUES (?, 589, ?, ?)", CITATIONS)
        conn.executemany(
            "INSERT INTO MultimediaTable (MediaID, MediaPath, MediaFile, Caption, RefNumber,"
            " Description, Date, SortDate, UTCModDate) VALUES (?, ?, ?, ?, '', '', '.', 0, 1.0)",
            [(mid, FOLDER, file, caption) for mid, file, caption in MEDIA])
        conn.executemany(
            "INSERT INTO MediaLinkTable (MediaID, OwnerType, OwnerID) VALUES (?, 4, ?)", MEDIA_LINKS)
        conn.commit()
        conn.close()

    def media(self, mid: int) -> tuple:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute(
                "SELECT Caption, RefNumber, Description, Date, SortDate FROM MultimediaTable"
                " WHERE MediaID = ?", (mid,)).fetchone()
        finally:
            conn.close()

    def test_dry_run_reports_and_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(death_index_media.main, str(self.db))

        self.assertEqual(code, 0)
        self.assertIn("3 media; 2 to update; 1 skipped\nDry run: nothing changed.", out)
        self.assertEqual(self.db.read_bytes(), before)
        text = self.output_path("death_index_media", "death_register").read_text(encoding="utf-8")
        for line in [
            f"   M3 {FOLDER}\\ROE-A-DRB-1910-Q2.jpg: attached to citations for different entries",
            f"   M2 {FOLDER}\\BRO-M-DRB-1988.jpg: Caption already 'Already set'",
            "   Caption:     Smith, John – death index – 1910 Q2",
        ]:
            self.assertIn(line + "\n", text)

    def test_apply_fills_empty_fields(self):
        code, out = self.run_main(death_index_media.main, str(self.db), "--apply")

        self.assertEqual(code, 0)
        self.assertIn("Applied: 2 media updated.", out)
        self.assertEqual(self.media(1), (
            "Smith, John – death index – 1910 Q2",
            "1910 Q2 Medway 2a 383",
            "Deaths registered in April, May, and June 1910: John Smith, age 60, Medway, vol. 2a,"
            " p. 383. Image of the General Register Office printed death index page, from FreeBMD.",
            "D-+19100400..+19100600..",
            sort_date("D-+19100400..+19100600.."),
        ))
        self.assertEqual(self.media(2), (
            "Already set",
            "1988 Sep Leeds 6 0307",
            "Deaths registered in 1988: Mary Brown, born 16 March 1901, Leeds, registered September"
            " 1988, vol. 6, p. 0307. Image of the General Register Office printed death index page,"
            " from FreeBMD.",
            "D.+19880900..+00000000..",
            sort_date("D.+19880900..+00000000.."),
        ))
        self.assertEqual(self.media(3)[0], "")

    def test_split_gives_each_entry_its_own_copy(self):
        code, out = self.run_main(death_index_media.main, str(self.db), "--split", "--apply")

        self.assertEqual(code, 0)
        self.assertIn("Applied: 4 media updated.", out)
        self.assertEqual(self.media(3)[:2], ("Roe, Ann – death index – 1910 Q2", "1910 Q2 Medway 2a 380"))
        conn = sqlite3.connect(self.db)
        copy = conn.execute(
            "SELECT m.MediaID, m.MediaFile, m.Thumbnail, m.Caption FROM MediaLinkTable l"
            " JOIN MultimediaTable m USING (MediaID) WHERE l.OwnerID = 13").fetchone()
        conn.close()
        self.assertEqual(copy, (4, "ROE-A-DRB-1910-Q2.jpg", b"\x01\x02", "Roe, Tom – death index – 1910 Q2"))

    def test_ancestry_register_entry(self):
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO CitationTable VALUES (20, 704, ?, ?)", (
            fields("entry for Ann Roe, born 11 July 1926, Sheffield, registered March 2000,"
                   " register C86A, district and subdistrict 0481C, entry 243",
                   "General Register Office, England and Wales Civil Registration Indexes"),
            "Deaths 2000\r\nRoe\tAnn\t11 Jul 1926\tSheffield\t03.00\tC86A\t0481C\t243"))
        conn.execute("INSERT INTO MultimediaTable (MediaID, MediaPath, MediaFile, Caption, RefNumber,"
                     " Description, Date, SortDate, UTCModDate) VALUES (9, 'x', 'ROE-A.pdf', '', '', '', '.', 0, 1.0)")
        conn.execute("INSERT INTO MediaLinkTable (MediaID, OwnerType, OwnerID) VALUES (9, 4, 20)")
        conn.commit()
        conn.close()
        code, _ = self.run_main(death_index_media.main, str(self.db), "--source", "704",
                                "--origin", "Ancestry record page, saved as PDF.", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.media(9)[:4], (
            "Roe, Ann – death index – 2000 Mar",
            "2000 Mar Sheffield C86A 0481C 243",
            "Deaths registered in 2000: Ann Roe, born 11 July 1926, Sheffield, registered March 2000,"
            " register C86A, district and subdistrict 0481C, entry 243. Ancestry record page, saved as PDF.",
            "D.+20000300..+00000000..",
        ))

    def test_no_arguments_prints_usage(self):
        code, out = self.run_main(death_index_media.main)
        self.assertEqual(code, 2)
        self.assertIn("Usage: python death_index_media.py", out)


if __name__ == "__main__":
    unittest.main()
