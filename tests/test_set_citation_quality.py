import sqlite3
import unittest

from support import ScriptTestCase

import set_citation_quality

SETUP_SQL = """
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER);
CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER, Quality TEXT,
    UTCModDate FLOAT);
INSERT INTO CitationTable VALUES (10, 583), (11, 583), (12, 999);
INSERT INTO CitationLinkTable VALUES (1, 10, '~~~', 1.0), (2, 11, 'PIX', 1.0), (3, 12, '~~~', 1.0);
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

    def test_rejects_bad_quality(self):
        code, out = self.run_main(set_citation_quality.main, str(self.db), "--source", "583", "--quality", "XYZ")
        self.assertEqual(code, 1)
        self.assertIn("is not information", out)


if __name__ == "__main__":
    unittest.main()
