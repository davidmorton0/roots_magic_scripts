import unittest

from support import ScriptTestCase

import task

BLANK = "0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0"
EXTRA = f"""
INSERT INTO PersonTable VALUES (1, 'U1', 0, 0, 0, {BLANK}, '', 1.0), (2, 'U2', 1, 0, 0, {BLANK}, '', 1.0);
INSERT INTO NameTable (OwnerID, Surname, Given, IsPrimary) VALUES (1, 'Smith', 'John', 1), (2, 'Brown', 'Mary', 1);
INSERT INTO TaskTable VALUES (1, 0, '', 'Find birth', 0, 4, '.', '.', '.', -1, -1, -1, '', 'line 1
line 2', '', 1.0, 0);
INSERT INTO TaskLinkTable VALUES (1, 1, 0, 1, 1.0);
"""


class TaskMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.use_full_schema(EXTRA)

    def run_task(self, *args: str) -> tuple[int, str]:
        return self.run_main(task.main, str(self.db), *args)

    def test_get(self):
        code, out = self.run_task("get", "1")
        self.assertEqual(code, 0)
        self.assertIn("T1  'Find birth'  (Status 0, Priority 4)", out)
        self.assertIn("   | line 2", out)
        self.assertIn("link -> P1 John Smith", out)
        self.assertIn("T1", self.run_task("get", "--person", "1")[1])
        self.assertIn("T1", self.run_task("get", "--name", "birth")[1])
        self.assertEqual(self.run_task("get", "--person", "2")[0], 1)
        self.assertEqual(self.run_task("get", "99")[0], 1)

    def test_create(self):
        before = self.db.read_bytes()
        args = ("create", "--name", "Find death", "--details", "a\nb", "--priority", "6", "--person", "2",
                "--set", "Results=r")
        self.assertEqual((self.run_task(*args)[0], self.db.read_bytes()), (0, before))
        code, out = self.run_task(*args, "--apply")
        self.assertEqual(code, 0)
        self.assertIn("Applied: task T2.", out)
        self.assertEqual(self.query("SELECT TaskType, RefNumber, Name, Status, Priority, Date1, SortDate3, Filename,"
                                    " Details, Results, Exclude FROM TaskTable WHERE TaskID = 2"),
                         [(0, "", "Find death", 0, 6, ".", -1, "", "a\nb", "r", 0)])
        self.assertEqual(self.query("SELECT OwnerType, OwnerID FROM TaskLinkTable WHERE TaskID = 2"), [(0, 2)])

    def test_create_refusals(self):
        code, out = self.run_task("create", "--name", "FIND BIRTH", "--person", "9", "--set", "Bad=1")
        self.assertEqual(code, 1)
        self.assertIn("T1 already has the name 'FIND BIRTH'", out)
        self.assertIn("P9 not found", out)
        self.assertIn("--set 'Bad' is not one of", out)

    def test_edit(self):
        code, out = self.run_task("edit", "1", "--priority", "6", "--status", "1", "--details", "new",
                                  "--link-person", "2", "--unlink-person", "1", "--apply")
        self.assertEqual(code, 0)
        row = self.query("SELECT Priority, Status, Details, UTCModDate FROM TaskTable WHERE TaskID = 1")[0]
        self.assertEqual(row[:3], (6, 1, "new"))
        self.assertGreater(row[3], 1.0)
        self.assertEqual(self.query("SELECT OwnerID FROM TaskLinkTable WHERE TaskID = 1"), [(2,)])

    def test_edit_refusals(self):
        code, out = self.run_task("edit", "1", "--link-person", "1", "--unlink-person", "2", "--link-person", "9")
        self.assertEqual(code, 1)
        self.assertIn("T1 is already linked to P1", out)
        self.assertIn("T1 is not linked to P2", out)
        self.assertIn("P9 not found", out)
        self.assertEqual(self.run_task("edit", "99", "--name", "x")[0], 1)
        self.assertEqual(self.run_task("edit", "1")[0], 1)
        self.run_task("create", "--name", "Other", "--apply")
        code, out = self.run_task("edit", "2", "--name", "find birth")
        self.assertIn("T1 already has the name 'find birth'", out)

    def test_delete(self):
        before = self.db.read_bytes()
        self.assertEqual((self.run_task("delete", "1")[0], self.db.read_bytes()), (0, before))
        self.assertEqual(self.run_task("delete", "1", "--apply")[0], 0)
        self.assertEqual(self.query("SELECT COUNT(*) FROM TaskTable"), [(0,)])
        self.assertEqual(self.query("SELECT COUNT(*) FROM TaskLinkTable"), [(0,)])
        self.assertEqual(self.run_task("delete", "99")[0], 1)


if __name__ == "__main__":
    unittest.main()
