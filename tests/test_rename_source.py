import sqlite3
import unittest

from support import ScriptTestCase

import rename_source

SETUP_SQL = """
CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, Name TEXT, UTCModDate FLOAT);
INSERT INTO SourceTable VALUES (583, 'Birth Register UK', 1.0), (590, 'Birth Register - UK - Ancestry', 1.0);
"""


class RenameSourceMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.commit()
        conn.close()

    def names(self) -> list[tuple]:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT SourceID, Name FROM SourceTable ORDER BY SourceID").fetchall()
        finally:
            conn.close()

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(rename_source.main, str(self.db), "583", "Birth Register - UK - FreeBMD")
        self.assertEqual(code, 0)
        self.assertIn("S583: 'Birth Register UK' -> 'Birth Register - UK - FreeBMD'", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply(self):
        code, _ = self.run_main(
            rename_source.main, str(self.db), "583", "Birth Register - UK - FreeBMD", "--apply"
        )
        self.assertEqual(code, 0)
        self.assertEqual(self.names()[0], (583, "Birth Register - UK - FreeBMD"))

    def test_refuses_existing_name(self):
        code, out = self.run_main(
            rename_source.main, str(self.db), "583", "birth register - uk - ancestry", "--apply"
        )
        self.assertEqual(code, 1)
        self.assertIn("already named", out)
        self.assertEqual(self.names()[0], (583, "Birth Register UK"))


if __name__ == "__main__":
    unittest.main()
