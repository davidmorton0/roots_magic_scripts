import sqlite3
import unittest

from support import ScriptTestCase

import link_citations_to_fact


def item(text: str) -> bytes:
    return (f"<Root><Fields><Field><Name>SpecificItem</Name><Value>{text}</Value></Field>"
            "</Fields></Root>").encode("utf-8")


SETUP_SQL = """
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, EventType INTEGER, OwnerType INTEGER,
    OwnerID INTEGER, IsPrimary INTEGER, Date TEXT);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER, Fields BLOB);
CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER, OwnerType INTEGER,
    OwnerID INTEGER, SortOrder INTEGER, Quality TEXT, IsPrivate INTEGER, Flags INTEGER,
    UTCModDate FLOAT);
INSERT INTO EventTable VALUES
    (1, 2, 0, 1, 1, 'D.+19100500..'), (2, 1, 0, 1, 1, 'D.+18500000..'),  -- person 1: Death, Birth
    (3, 2, 0, 2, 1, '.'),                                                 -- person 2: no Birth
    (4, 2, 0, 3, 1, '.'), (5, 1, 0, 3, 1, '.');                           -- person 3: already on Birth
INSERT INTO CitationLinkTable (CitationID, OwnerType, OwnerID, Quality) VALUES
    (10, 2, 1, 'PIX'), (11, 2, 3, 'PIX'), (12, 2, 4, 'PIX'), (12, 2, 5, 'SIX'), (13, 2, 1, 'PIX');
"""


class LinkCitationsToFactMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.executemany("INSERT INTO CitationTable VALUES (?, 589, ?)", [
            (10, item("entry for John Smith, age 60, Medway")),
            (11, item("entry for Mary Brown, age 40, Leeds")),
            (12, item("entry for Albert Brown, age 2, Leeds")),
            (13, item("entry for John Smith, Medway")),  # no age: not matched
        ])
        conn.commit()
        conn.close()

    def args(self, *extra: str) -> tuple:
        return (link_citations_to_fact.main, str(self.db), "--source", "589", "--fact", "1",
                "--item", ", age ", "--quality", "SIX", *extra)

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(*self.args())

        self.assertEqual(code, 0)
        self.assertIn("1 links to add; 1 not linked\nDry run: nothing changed.", out)
        self.assertEqual(self.db.read_bytes(), before)
        text = self.output_path("link_citations_to_fact").read_text(encoding="utf-8")
        self.assertIn("   C11 Dr Mary Brown [P2]: person has no such event\n", text)
        self.assertIn("   C10 -> E2 D.+18500000.. John smith [P1]\n", text)

    def test_apply_adds_link_with_quality(self):
        code, out = self.run_main(*self.args("--apply"))

        self.assertEqual(code, 0)
        self.assertIn("Applied: 1 citation links added.", out)
        conn = sqlite3.connect(self.db)
        row = conn.execute(
            "SELECT CitationID, OwnerType, OwnerID, SortOrder, Quality, IsPrivate, Flags"
            " FROM CitationLinkTable ORDER BY LinkID DESC LIMIT 1").fetchone()
        conn.close()
        self.assertEqual(row, (10, 2, 2, 0, "SIX", 0, 0))

    def test_rejects_bad_quality(self):
        code, out = self.run_main(link_citations_to_fact.main, str(self.db), "--source", "589",
                                  "--fact", "1", "--item", "x", "--quality", "ABC")
        self.assertEqual(code, 1)
        self.assertIn("is not information", out)

    def test_no_arguments_prints_usage(self):
        code, out = self.run_main(link_citations_to_fact.main)
        self.assertEqual(code, 2)
        self.assertIn("Usage: python link_citations_to_fact.py", out)


if __name__ == "__main__":
    unittest.main()
