import sqlite3
import unittest

from support import ScriptTestCase

import set_citation_text

SETUP_SQL = """
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, ActualText TEXT, UTCModDate FLOAT);
INSERT INTO CitationTable VALUES (10, '', 1.0), (11, 'already', 1.0);
"""


class SetCitationTextMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.commit()
        conn.close()

    def texts(self) -> list[tuple]:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT CitationID, ActualText FROM CitationTable ORDER BY 1").fetchall()
        finally:
            conn.close()

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(set_citation_text.main, str(self.db), "--text", "10", "a\nb")
        self.assertEqual(code, 0)
        self.assertIn("C10:\n   a\n   b\n", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply(self):
        code, _ = self.run_main(set_citation_text.main, str(self.db), "--text", "10", "a\nb", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.texts()[0], (10, "a\nb"))

    def test_refuses_to_overwrite(self):
        code, out = self.run_main(set_citation_text.main, str(self.db), "--text", "11", "x", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("already have a transcription: [11]", out)
        self.assertEqual(self.texts()[1], (11, "already"))


if __name__ == "__main__":
    unittest.main()
