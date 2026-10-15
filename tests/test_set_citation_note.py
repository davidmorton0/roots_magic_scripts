import sqlite3
import unittest

from support import ScriptTestCase

import set_citation_note

SETUP_SQL = """
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, Comments TEXT, UTCModDate FLOAT);
INSERT INTO CitationTable VALUES (10, 'old', 1.0), (11, '', 1.0);
"""


class SetCitationNoteMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.commit()
        conn.close()

    def notes(self) -> list[tuple]:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT CitationID, Comments FROM CitationTable ORDER BY 1").fetchall()
        finally:
            conn.close()

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(set_citation_note.main, str(self.db), "--note", "10", "new")
        self.assertEqual(code, 0)
        self.assertIn("C10: 'old' -> 'new'", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply_two_notes(self):
        code, _ = self.run_main(set_citation_note.main, str(self.db),
                                "--note", "10", "a", "--note", "11", "b", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.notes(), [(10, "a"), (11, "b")])

    def test_unknown_citation(self):
        code, out = self.run_main(set_citation_note.main, str(self.db), "--note", "99", "x")
        self.assertEqual(code, 1)
        self.assertIn("Citations not found: [99]", out)


if __name__ == "__main__":
    unittest.main()
