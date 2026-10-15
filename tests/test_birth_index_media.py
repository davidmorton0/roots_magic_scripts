import sqlite3
import unittest

from support import ScriptTestCase

import birth_index_media

FOLDER = "H:\\My Drive\\Records\\Births\\Britain\\Registers"
CITING_Q1 = "General Register Office, Births registered in January, February, and March 1886"
CITING_Q3 = "General Register Office, Births registered in July, August, and September 1960"
ORIGIN = "Image of the General Register Office printed birth index page, from FreeBMD."


def fields(item: str, citing: str) -> bytes:
    return (
        "<Root><Fields>"
        "<Field><Name>AccessDate</Name><Value>3 August 2008</Value></Field>"
        f"<Field><Name>SpecificItem</Name><Value>{item}</Value></Field>"
        f"<Field><Name>Citing</Name><Value>{citing}</Value></Field>"
        "</Fields></Root>"
    ).encode("utf-8")


SETUP_SQL = """
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, EventType INTEGER, OwnerType INTEGER,
    OwnerID INTEGER, Date TEXT, SortDate BIGINT);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER, Fields BLOB,
    ActualText TEXT);
CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER,
    OwnerType INTEGER, OwnerID INTEGER);
CREATE TABLE MultimediaTable (MediaID INTEGER PRIMARY KEY, MediaPath TEXT, MediaFile TEXT,
    Caption TEXT, RefNumber TEXT, Description TEXT, Date TEXT, SortDate BIGINT,
    UTCModDate FLOAT);
CREATE TABLE MediaLinkTable (LinkID INTEGER PRIMARY KEY, MediaID INTEGER, OwnerType INTEGER,
    OwnerID INTEGER);

INSERT INTO EventTable VALUES
    (1, 1024, 0, 1, 'D-+18860100..+18860300..', 111),
    (2, 1, 0, 1, 'D.+18860214..+00000000..', 222),
    (3, 1024, 0, 2, 'D-+19600700..+19600900..', 333),
    (4, 1024, 0, 3, 'D-+19600700..+19600900..', 444);
"""
CITATIONS = [
    # CitationID, Fields, ActualText
    (10, fields("entry for John smith, Medway, vol. 2a, p. 602", CITING_Q1),
     "Births Mar 1886\nSmith John Medway 2a 602"),
    (11, fields("entry for John smith, Medway, vol. 2a, p. 602", CITING_Q1),
     "Births Mar 1886\nSmith John Medway 2a 602"),
    (12, fields("entry for Mary Brown, Leeds, vol. 2c, p. 533, mother's maiden name Roe",
                CITING_Q3), "Births Sep 1960\nBROWN MARY ROE LEEDS 2c 533"),
    (13, fields("entry for Albert Brown, Leeds, vol. 2c, p. 1", CITING_Q3),
     "Births Sep 1960\nBrown Albert Leeds 2c 1"),
    (14, fields("entry for Albert Brown, Leeds, vol. 2c, p. 2", CITING_Q3),
     "Births Sep 1960\nBrown Albert Leeds 2c 2"),
    (15, fields("entry for Mary Brown, Leeds, vol. 2c, p. 533", CITING_Q3),
     "Name: \tMary Brown\nRegistration Quarter: \tJul-Aug-Sep"),
]
CITATION_LINKS = [(10, 2, 1), (11, 2, 2), (12, 2, 3), (13, 2, 4), (14, 2, 4), (15, 2, 3)]
MEDIA = [
    # MediaID, MediaFile, Caption, Date, SortDate
    (1, "SMI-J-BRG-1886-Q1.tif", "", ".", 9223372036854775807),
    (2, "BRO-M-BRG-1960-Q3.jpg", "My own caption", ".", 0),
    (3, "BRO-A-BRG-1960-Q3.jpg", "", ".", 9223372036854775807),
    (4, "BRO-M-BRG-1960-Q3-ancestry.jpg", "", ".", 9223372036854775807),
]
MEDIA_LINKS = [(1, 4, 10), (1, 4, 11), (2, 4, 12), (3, 4, 13), (3, 4, 14), (4, 4, 15)]


class BirthIndexMediaMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.executemany("INSERT INTO CitationTable VALUES (?, 583, ?, ?)", CITATIONS)
        conn.executemany(
            "INSERT INTO CitationLinkTable (CitationID, OwnerType, OwnerID) VALUES (?, ?, ?)",
            CITATION_LINKS,
        )
        conn.executemany(
            "INSERT INTO MultimediaTable (MediaID, MediaPath, MediaFile, Caption, RefNumber,"
            " Description, Date, SortDate) VALUES (?, ?, ?, ?, '', '', ?, ?)",
            [(m, FOLDER, f, c, d, s) for m, f, c, d, s in MEDIA],
        )
        conn.executemany(
            "INSERT INTO MediaLinkTable (MediaID, OwnerType, OwnerID) VALUES (?, ?, ?)",
            MEDIA_LINKS,
        )
        conn.commit()
        conn.close()

    def media(self, media_id: int) -> tuple:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute(
                "SELECT Caption, RefNumber, Description, Date, SortDate FROM MultimediaTable"
                " WHERE MediaID = ?",
                (media_id,),
            ).fetchone()
        finally:
            conn.close()

    def test_dry_run_reports_and_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(birth_index_media.main, str(self.db))

        self.assertEqual(code, 0)
        self.assertIn("4 media; 2 to update; 2 skipped\nDry run: nothing changed.", out)
        self.assertEqual(self.db.read_bytes(), before)
        text = self.output_path("birth_index_media", "birth_register").read_text(encoding="utf-8")
        for line in [
            f"   M3 {FOLDER}\\BRO-A-BRG-1960-Q3.jpg: attached to citations for different people or entries",
            f"   M4 {FOLDER}\\BRO-M-BRG-1960-Q3-ancestry.jpg: C15: transcription not from FreeBMD,"
            " so the image's origin is unknown",
            f"   M2 {FOLDER}\\BRO-M-BRG-1960-Q3.jpg: Caption already 'My own caption'",
            "   Caption:     smith, John – birth index – 1886 Q1",
        ]:
            self.assertIn(line + "\n", text)

    def test_apply_fills_all_fields(self):
        code, out = self.run_main(birth_index_media.main, str(self.db), "--apply")

        self.assertEqual(code, 0)
        self.assertIn("Applied: 2 media updated.", out)
        # Register event's date preferred over the plain Birth event's.
        self.assertEqual(
            self.media(1),
            (
                "smith, John – birth index – 1886 Q1",
                "1886 Q1 Medway 2a 602",
                f"{CITING_Q1.removeprefix('General Register Office, ')}: John smith, Medway,"
                f" vol. 2a, p. 602. {ORIGIN}",
                "D-+18860100..+18860300..",
                111,
            ),
        )

    def test_apply_keeps_existing_caption_and_sets_date_with_sort_date(self):
        self.run_main(birth_index_media.main, str(self.db), "--apply")

        caption, ref, descr, date, sort_date = self.media(2)
        self.assertEqual(caption, "My own caption")
        self.assertEqual(ref, "1960 Q3 Leeds 2c 533")
        self.assertIn("Mary Brown, Leeds, vol. 2c, p. 533, mother's maiden name Roe", descr)
        self.assertEqual((date, sort_date), ("D-+19600700..+19600900..", 333))

    def test_skipped_media_unchanged(self):
        self.run_main(birth_index_media.main, str(self.db), "--apply")
        self.assertEqual(self.media(3), ("", "", "", ".", 9223372036854775807))
        self.assertEqual(self.media(4), ("", "", "", ".", 9223372036854775807))

    def test_no_arguments_prints_usage(self):
        code, out = self.run_main(birth_index_media.main)
        self.assertEqual(code, 2)
        self.assertIn("Usage: python birth_index_media.py", out)


if __name__ == "__main__":
    unittest.main()
