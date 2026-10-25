import sqlite3
import unittest

from support import ScriptTestCase

import set_source_text


class SetSourceTextMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript("""
            CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, Name TEXT, ActualText TEXT,
                Comments TEXT, UTCModDate FLOAT);
            INSERT INTO SourceTable VALUES (1, 'Index', 'example.org', '', 1.0), (2, 'Other', 'x', '', 1.0);
        """)
        conn.commit()
        conn.close()

    def texts(self) -> list[tuple]:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT SourceID, ActualText FROM SourceTable ORDER BY SourceID").fetchall()
        finally:
            conn.close()

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(set_source_text.main, str(self.db), "--text", "1", "Index pages")
        self.assertEqual(code, 0)
        self.assertIn("S1 'Index'\n   'example.org'\n   -> 'Index pages'\nDry run: nothing changed.", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply_sets_only_the_named_source(self):
        code, out = self.run_main(set_source_text.main, str(self.db), "--text", "1", "Index pages", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.texts(), [(1, "Index pages"), (2, "x")])

    def test_note_sets_comments_not_text(self):
        code, out = self.run_main(set_source_text.main, str(self.db), "--text", "1", "Dates unreliable", "--note",
                                  "--apply")
        self.assertEqual(code, 0)
        self.assertIn("Applied: 1 source notes set.", out)
        conn = sqlite3.connect(self.db)
        try:
            row = conn.execute("SELECT ActualText, Comments FROM SourceTable WHERE SourceID = 1").fetchone()
        finally:
            conn.close()
        self.assertEqual(row, ("example.org", "Dates unreliable"))

    def test_missing_source(self):
        code, out = self.run_main(set_source_text.main, str(self.db), "--text", "9", "x")
        self.assertEqual(code, 1)
        self.assertIn("Sources not found: S9", out)

    def test_no_arguments_prints_usage(self):
        code, out = self.run_main(set_source_text.main)
        self.assertEqual(code, 2)
        self.assertIn("Usage: python set_source_text.py", out)


if __name__ == "__main__":
    unittest.main()
