import sqlite3
import unittest

from support import ScriptTestCase

import rename_person


class RenamePersonMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript("""
            ALTER TABLE NameTable ADD COLUMN GivenMP TEXT;
            ALTER TABLE NameTable ADD COLUMN SurnameMP TEXT;
            ALTER TABLE NameTable ADD COLUMN UTCModDate FLOAT;
            UPDATE NameTable SET GivenMP = Given, SurnameMP = Surname WHERE OwnerID = 2;
        """)
        conn.commit()
        conn.close()

    def name(self, pid: int) -> tuple:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT Given, Surname, GivenMP, SurnameMP FROM NameTable"
                                " WHERE OwnerID = ? AND IsPrimary = 1", (pid,)).fetchone()
        finally:
            conn.close()

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(rename_person.main, str(self.db), "--person", "1", "--given", "Jon")
        self.assertEqual(code, 0)
        self.assertIn("P1: John smith -> Jon smith", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_given_only_on_an_older_row(self):
        code, _ = self.run_main(rename_person.main, str(self.db), "--person", "1", "--given", "Jon", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.name(1), ("Jon", "smith", None, None))

    def test_both_names_follow_into_the_mp_columns(self):
        self.run_main(rename_person.main, str(self.db), "--person", "2", "--given", "Maria", "--surname", "Browne",
                      "--apply")
        self.assertEqual(self.name(2), ("Maria", "Browne", "Maria", "Browne"))
        self.assertEqual(self.name(3)[:2], ("Albert", "Brown"))  # others untouched

    def test_refusals(self):
        code, out = self.run_main(rename_person.main, str(self.db), "--person", "4", "--given", "X", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("no primary name", out)
        code, out = self.run_main(rename_person.main, str(self.db), "--person", "1")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
