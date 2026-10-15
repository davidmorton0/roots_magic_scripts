import sqlite3
import unittest

from support import ScriptTestCase

import birth_index_media_dates
from rmutils import sort_date


def fields(first_months: str, year: int) -> bytes:
    citing = f"General Register Office, Births registered in {first_months} {year}"
    return f"<Root><Fields><Field><Name>Citing</Name><Value>{citing}</Value></Field></Fields></Root>".encode()


SETUP_SQL = """
CREATE TABLE MultimediaTable (MediaID INTEGER PRIMARY KEY, MediaFile TEXT, Date TEXT,
    SortDate BIGINT, UTCModDate FLOAT);
CREATE TABLE MediaLinkTable (LinkID INTEGER PRIMARY KEY, MediaID INTEGER, OwnerType INTEGER,
    OwnerID INTEGER);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER, Fields BLOB);
INSERT INTO MultimediaTable VALUES
    (1, 'a.jpg', 'D-+18860100.A+18860300..', 1, 1.0),   -- about, same quarter: changes
    (2, 'b.jpg', 'DR+18860100..+18860300..', 2, 1.0),   -- between, same quarter: changes
    (3, 'c.jpg', 'D-+18860100..+18860300..', 3, 1.0),   -- already plain
    (4, 'd.jpg', 'DR+18860400.A+18860300..', 4, 1.0),   -- broken: listed
    (5, 'e.jpg', '.', 5, 1.0);                          -- blank: left alone
INSERT INTO MediaLinkTable (MediaID, OwnerType, OwnerID) VALUES (1, 4, 10), (2, 4, 10), (3, 4, 10), (4, 4, 10), (5, 4, 10);
"""


class BirthIndexMediaDatesMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.execute("INSERT INTO CitationTable VALUES (10, 583, ?)",
                     (fields("January, February, and March", 1886),))
        conn.commit()
        conn.close()

    def dates(self) -> list[tuple]:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT MediaID, Date, SortDate FROM MultimediaTable ORDER BY MediaID").fetchall()
        finally:
            conn.close()

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(birth_index_media_dates.main, str(self.db))
        self.assertEqual(code, 0)
        self.assertIn("2 scan dates to change; 1 listed\nDry run: nothing changed.", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply(self):
        target = "D-+18860100..+18860300.."
        code, out = self.run_main(birth_index_media_dates.main, str(self.db), "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.dates(), [
            (1, target, sort_date(target)), (2, target, sort_date(target)), (3, target, 3),
            (4, "DR+18860400.A+18860300..", 4), (5, ".", 5),
        ])

    def test_include_sets_listed_scan(self):
        target = "D-+18860100..+18860300.."
        self.run_main(birth_index_media_dates.main, str(self.db), "--include", "4", "--apply")
        self.assertEqual(self.dates()[3], (4, target, sort_date(target)))


if __name__ == "__main__":
    unittest.main()
