import sqlite3
import unittest

from support import ScriptTestCase

import create_task

SETUP_SQL = """
CREATE TABLE TaskTable (TaskID INTEGER PRIMARY KEY, TaskType INTEGER, RefNumber TEXT, Name TEXT,
    Status INTEGER, Priority INTEGER, Date1 TEXT, Date2 TEXT, Date3 TEXT, SortDate1 BIGINT,
    SortDate2 BIGINT, SortDate3 BIGINT, Filename TEXT, Details TEXT, Results TEXT,
    UTCModDate FLOAT, Exclude INTEGER);
CREATE TABLE TaskLinkTable (LinkID INTEGER PRIMARY KEY, TaskID INTEGER, OwnerType INTEGER,
    OwnerID INTEGER, UTCModDate FLOAT);
"""


class CreateTaskMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.commit()
        conn.close()

    def query(self, sql: str) -> list[tuple]:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute(sql).fetchall()
        finally:
            conn.close()

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(create_task.main, str(self.db), "--person", "1",
                                  "--name", "Check birth", "--details", "line 1\nline 2")
        self.assertEqual(code, 0)
        self.assertIn("linked to John smith [P1]", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply_and_refuse_duplicate(self):
        args = ["--person", "1", "--name", "Check birth", "--details", "line 1"]
        code, _ = self.run_main(create_task.main, str(self.db), *args, "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(
            self.query("SELECT TaskType, Name, Status, Priority, Date1, SortDate1, Details FROM TaskTable"),
            [(0, "Check birth", 0, 4, ".", -1, "line 1")],
        )
        self.assertEqual(self.query("SELECT TaskID, OwnerType, OwnerID FROM TaskLinkTable"), [(1, 0, 1)])
        code, out = self.run_main(create_task.main, str(self.db), *args, "--apply")
        self.assertEqual(code, 1)
        self.assertIn("already has the name", out)

    def test_unknown_person(self):
        code, out = self.run_main(create_task.main, str(self.db), "--person", "99",
                                  "--name", "x", "--details", "y")
        self.assertEqual(code, 1)
        self.assertIn("Person P99 not found", out)


if __name__ == "__main__":
    unittest.main()
