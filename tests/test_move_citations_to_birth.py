import sqlite3
import unittest

from support import ScriptTestCase

import move_citations_to_birth

CITING_Q1_1886 = "General Register Office, Births registered in January, February, and March 1886"


def fields(citing: str) -> bytes:
    return (
        "<Root><Fields>"
        f"<Field><Name>Citing</Name><Value>{citing}</Value></Field>"
        "</Fields></Root>"
    ).encode("utf-8")


SETUP_SQL = """
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, EventType INTEGER, OwnerType INTEGER,
    OwnerID INTEGER, IsPrimary INTEGER, Date TEXT);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER, Fields BLOB);
CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER,
    OwnerType INTEGER, OwnerID INTEGER, Quality TEXT, UTCModDate FLOAT);

INSERT INTO EventTable VALUES
    -- person 1: register event 1, Birth event 2 (fits the quarter)
    (1, 1024, 0, 1, 0, 'D-+18860100..+18860300..'),
    (2, 1, 0, 1, 1, 'D.+18860214..+00000000..'),
    -- person 2: register event 3, Birth event 4 dated after the quarter
    (3, 1024, 0, 2, 0, 'D-+18860100..+18860300..'),
    (4, 1, 0, 2, 0, 'D.+18870000..+00000000..'),
    -- person 3: register event 5, no Birth event
    (5, 1024, 0, 3, 0, 'D-+18860100..+18860300..'),
    -- person 4: register event 6, two primary Birth events
    (6, 1024, 0, 4, 0, 'D-+18860100..+18860300..'),
    (7, 1, 0, 4, 1, 'D.+18860100..+00000000..'),
    (8, 1, 0, 4, 1, 'D.+18860200..+00000000..');
"""
CITATIONS = [(10,), (11,), (12,), (13,), (14,)]
LINKS = [
    # LinkID, CitationID, OwnerType, OwnerID, Quality
    (100, 10, 2, 1, "~~~"),
    (101, 11, 2, 3, "~~~"),
    (102, 12, 2, 5, "~~~"),
    (103, 13, 2, 6, "~~~"),
    (104, 14, 2, 1, "~~~"),
    (105, 14, 2, 2, "~~~"),  # citation 14 is already on person 1's Birth event
    (106, 15, 2, 1, "~~"),  # citation 15 is from another source
]


class MoveCitationsToBirthMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.executemany(
            "INSERT INTO CitationTable VALUES (?, 583, ?)",
            [(cid, fields(CITING_Q1_1886)) for (cid,) in CITATIONS],
        )
        conn.execute("INSERT INTO CitationTable VALUES (15, 999, ?)", (b"<Root></Root>",))
        conn.executemany(
            "INSERT INTO CitationLinkTable VALUES (?, ?, ?, ?, ?, 1.0)", LINKS
        )
        conn.commit()
        conn.close()

    def links(self) -> list[tuple]:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute(
                "SELECT LinkID, CitationID, OwnerType, OwnerID, Quality FROM CitationLinkTable"
                " ORDER BY LinkID"
            ).fetchall()
        finally:
            conn.close()

    def test_dry_run_reports_and_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(move_citations_to_birth.main, str(self.db))

        self.assertEqual(code, 0)
        self.assertIn("6 citation links; 3 to move; 3 not moved\nDry run: nothing changed.", out)
        self.assertEqual(self.db.read_bytes(), before)
        text = self.output_path("move_citations_to_birth", "birth_register").read_text(encoding="utf-8")
        for line in [
            "   C12 Albert Brown, Jr [P3]: person has no Birth event",
            "   C13 (no primary name) [P4]: person has 2 primary Birth events",
            "   C14 John smith [P1]: Birth event E2 already has this citation",
            "   C11 Dr Mary Brown [P2]: Birth date is after the registration quarter"
            " (Birth D.+18870000..+00000000.., register D-+18860100..+18860300..)",
            "   C10 John smith [P1]: E1 D-+18860100..+18860300.. -> E2 D.+18860214..+00000000..",
        ]:
            self.assertIn(line + "\n", text)

    def test_apply_moves_links_in_place(self):
        code, out = self.run_main(move_citations_to_birth.main, str(self.db), "--apply")

        self.assertEqual(code, 0)
        self.assertIn("Applied: 3 citation links moved.", out)
        self.assertEqual(
            self.links(),
            [
                (100, 10, 2, 2, "~~~"),
                (101, 11, 2, 4, "~~~"),
                (102, 12, 2, 5, "~~~"),
                (103, 13, 2, 6, "~~~"),
                (104, 14, 2, 1, "~~~"),
                (105, 14, 2, 2, "~~~"),
                (106, 15, 2, 2, "~~"),
            ],
        )

    def test_no_arguments_prints_usage(self):
        code, out = self.run_main(move_citations_to_birth.main)
        self.assertEqual(code, 2)
        self.assertIn("Usage: python move_citations_to_birth.py", out)


if __name__ == "__main__":
    unittest.main()
