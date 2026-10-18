import sqlite3
import unittest

from support import ScriptTestCase

import birth_dates_before

LOW = 17178820620


def sort_date(year: int, month: int, day: int = 0) -> int:
    return ((year + 10000) << 49) | (month << 45) | (day << 39) | LOW


def citation_fields(first_months: str, year: int) -> bytes:
    citing = f"General Register Office, Births registered in {first_months} {year}"
    return (
        f"<Root><Fields><Field><Name>Citing</Name><Value>{citing}</Value></Field></Fields></Root>"
    ).encode("utf-8")


SETUP_SQL = """
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, EventType INTEGER, OwnerType INTEGER,
    OwnerID INTEGER, Date TEXT, SortDate BIGINT, UTCModDate FLOAT);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER, Fields BLOB);
CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER,
    OwnerType INTEGER, OwnerID INTEGER);
CREATE TABLE MultimediaTable (MediaID INTEGER PRIMARY KEY, Date TEXT, SortDate BIGINT);

INSERT INTO EventTable VALUES
    -- quarter "between" with about, Jan-Mar 1886: changes to before April 1886
    (1, 1, 0, 1, 'DR+18860100.A+18860300..', 1, 1.0),
    -- quarter range, Oct-Dec 1890: changes to before January 1891
    (2, 1, 0, 2, 'D-+18901000..+18901200..', 2, 1.0),
    -- exact day: left alone
    (3, 1, 0, 3, 'D.+18860214..+00000000..', 3, 1.0),
    -- quarter differs from the citation's: left alone and listed
    (4, 1, 0, 4, 'DR+18910700..+18910900..', 4, 1.0),
    -- quarter-only Birth cited only by another source: left alone
    (5, 1, 0, 1, 'DR+18700100..+18700300..', 5, 1.0);
"""


class BirthDatesBeforeMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.executemany(
            "INSERT INTO CitationTable VALUES (?, ?, ?)",
            [
                (10, 583, citation_fields("January, February, and March", 1886)),
                (11, 583, citation_fields("October, November, and December", 1890)),
                (12, 583, citation_fields("January, February, and March", 1886)),
                (13, 583, citation_fields("July, August, and September", 1890)),
                (14, 999, citation_fields("January, February, and March", 1870)),
            ],
        )
        conn.executemany(
            "INSERT INTO CitationLinkTable (CitationID, OwnerType, OwnerID) VALUES (?, 2, ?)",
            [(10, 1), (11, 2), (12, 3), (13, 4), (14, 5)],
        )
        conn.commit()
        conn.close()

    def events(self) -> list[tuple]:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute(
                "SELECT EventID, Date, SortDate FROM EventTable ORDER BY EventID"
            ).fetchall()
        finally:
            conn.close()

    def test_dry_run_reports_and_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(birth_dates_before.main, str(self.db))

        self.assertEqual(code, 0)
        self.assertIn("2 Birth dates to change; 1 left alone\nDry run: nothing changed.", out)
        self.assertEqual(self.db.read_bytes(), before)
        text = self.output_path("birth_dates_before", "birth_register").read_text(encoding="utf-8")
        self.assertIn(
            "   E4 (no primary name) [P4] DR+18910700..+18910900..:"
            " date's quarter differs from the citation's registration quarter\n",
            text,
        )

    def test_apply_writes_before_dates_with_sort_dates(self):
        code, out = self.run_main(birth_dates_before.main, str(self.db), "--apply")

        self.assertEqual(code, 0)
        self.assertIn("Applied: 2 Birth dates changed.", out)
        self.assertEqual(
            self.events(),
            [
                # value RootsMagic 12 wrote for "Bef Apr 1886"
                (1, "DB+18860400..+00000000..", 6691363901032890368),
                (2, "DB+18910100..+00000000..", sort_date(1891, 1) - 12),
                (3, "D.+18860214..+00000000..", 3),
                (4, "DR+18910700..+18910900..", 4),
                (5, "DR+18700100..+18700300..", 5),
            ],
        )

    def test_uses_existing_sort_date_for_the_same_string(self):
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO MultimediaTable VALUES (1, 'DB+18910100..+00000000..', 42)")
        conn.commit()
        conn.close()

        self.run_main(birth_dates_before.main, str(self.db), "--apply")
        self.assertEqual(self.events()[1], (2, "DB+18910100..+00000000..", 42))

    def test_death_fact(self):
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO EventTable VALUES (6, 2, 0, 2, 'D-+19040700.A+19040900..', 6, 1.0)")
        citing = "General Register Office, Deaths registered in July, August, and September 1904"
        conn.execute("INSERT INTO CitationTable VALUES (15, 589, ?)", (
            f"<Root><Fields><Field><Name>Citing</Name><Value>{citing}</Value></Field></Fields></Root>"
            .encode("utf-8"),))
        conn.execute("INSERT INTO CitationLinkTable (CitationID, OwnerType, OwnerID) VALUES (15, 2, 6)")
        conn.commit()
        conn.close()
        code, out = self.run_main(birth_dates_before.main, str(self.db), "--source", "589",
                                  "--fact", "2", "--folder", "death_register", "--apply")

        self.assertEqual(code, 0)
        self.assertIn("1 Death dates to change; 0 left alone", out)
        self.assertTrue(self.output_path("birth_dates_before", "death_register").is_file())
        self.assertEqual(self.events()[5], (6, "DB+19041000..+00000000..", sort_date(1904, 10) - 12))

    def test_no_arguments_prints_usage(self):
        code, out = self.run_main(birth_dates_before.main)
        self.assertEqual(code, 2)
        self.assertIn("Usage: python birth_dates_before.py", out)


if __name__ == "__main__":
    unittest.main()
