import sqlite3
import unittest

from support import ScriptTestCase

import set_citation_quality

SETUP_SQL = """
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER, Fields BLOB);
CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER, Quality TEXT,
    UTCModDate FLOAT, OwnerType INTEGER DEFAULT 2, OwnerID INTEGER DEFAULT 0);
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, EventType INTEGER);
INSERT INTO CitationTable VALUES (10, 583, NULL), (11, 583, NULL), (12, 999, NULL);
INSERT INTO CitationLinkTable (LinkID, CitationID, Quality, UTCModDate) VALUES
    (1, 10, '~~~', 1.0), (2, 11, 'PIX', 1.0), (3, 12, '~~~', 1.0);
"""


class SetCitationQualityMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.commit()
        conn.close()

    def qualities(self) -> list[tuple]:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT LinkID, Quality FROM CitationLinkTable ORDER BY LinkID").fetchall()
        finally:
            conn.close()

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(set_citation_quality.main, str(self.db), "--source", "583", "--quality", "PIX")
        self.assertEqual(code, 0)
        self.assertIn("Citation links: 2; set to 'PIX': 1; already assessed, kept: 1", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply_sets_only_unassessed_links_of_the_source(self):
        code, _ = self.run_main(
            set_citation_quality.main, str(self.db), "--source", "583", "--quality", "SDX", "--apply"
        )
        self.assertEqual(code, 0)
        self.assertEqual(self.qualities(), [(1, "SDX"), (2, "PIX"), (3, "~~~")])

    def test_fact_and_item_filters(self):
        def item(text):
            return f"<Root><Fields><Field><Name>SpecificItem</Name><Value>{text}</Value></Field></Fields></Root>"

        conn = sqlite3.connect(self.db)
        conn.executescript("""
            INSERT INTO EventTable VALUES (100, 2), (101, 1), (102, 1);
            INSERT INTO CitationLinkTable (LinkID, CitationID, Quality, UTCModDate, OwnerType, OwnerID) VALUES
                (4, 20, '~~~', 1.0, 2, 100), (5, 20, '~~~', 1.0, 2, 101),
                (6, 21, '~~~', 1.0, 2, 102), (7, 21, '~~~', 1.0, 0, 102);
        """)
        conn.executemany("INSERT INTO CitationTable VALUES (?, 589, ?)", [
            (20, item("entry for John Smith, age 60, Medway")),
            (21, item("entry for Mary Brown, born 9 October 1892, Leeds")),
        ])
        conn.commit()
        conn.close()
        common = (set_citation_quality.main, str(self.db), "--source", "589")
        self.run_main(*common, "--quality", "PIX", "--fact", "2", "--apply")
        self.run_main(*common, "--quality", "SDX", "--fact", "1", "--item", r"born \d", "--apply")
        code, out = self.run_main(*common, "--quality", "SIX", "--fact", "1", "--not-item", r"born \d",
                                  "--apply")
        self.assertEqual(code, 0)
        self.assertIn("Citation links: 1; set to 'SIX': 1;", out)
        self.assertEqual(self.qualities()[3:], [(4, "PIX"), (5, "SIX"), (6, "SDX"), (7, "~~~")])

    def test_rejects_bad_quality(self):
        code, out = self.run_main(set_citation_quality.main, str(self.db), "--source", "583", "--quality", "XYZ")
        self.assertEqual(code, 1)
        self.assertIn("is not information", out)


if __name__ == "__main__":
    unittest.main()
