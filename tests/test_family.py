import unittest

from support import ScriptTestCase

import family

BLANK = "0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0"
EXTRA = f"""
INSERT INTO PersonTable VALUES
    (1, 'U1', 0, 0, 0, {BLANK}, '', 1.0), (2, 'U2', 1, 0, 0, {BLANK}, '', 1.0),
    (3, 'U3', 0, 0, 0, {BLANK}, '', 1.0), (4, 'U4', 1, 0, 0, {BLANK}, '', 1.0),
    (5, 'U5', 0, 0, 0, {BLANK}, '', 1.0), (6, 'U6', 1, 0, 0, {BLANK}, '', 1.0);
INSERT INTO NameTable (OwnerID, Surname, Given, IsPrimary) VALUES (1, 'Smith', 'John', 1), (2, 'Smith', 'Mary', 1),
    (3, 'Smith', 'Tom', 1), (4, 'Brown', 'Ann', 1), (5, 'Smith', 'Bob', 1), (6, 'Smith', 'Jill', 1);
INSERT INTO FamilyTable (FamilyID, FatherID, MotherID, ChildID, Note) VALUES (1, 1, 2, 3, 'old'), (2, 5, 0, 0, '');
INSERT INTO ChildTable (RecID, ChildID, FamilyID, ChildOrder) VALUES (1, 3, 1, 1), (2, 6, 1, 2);
UPDATE PersonTable SET SpouseID = 1 WHERE PersonID IN (1, 2);
UPDATE PersonTable SET SpouseID = 2 WHERE PersonID = 5;
UPDATE PersonTable SET ParentID = 1 WHERE PersonID IN (3, 6);
"""


class FamilyMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.use_full_schema(EXTRA)

    def run_family(self, *args: str) -> tuple[int, str]:
        return self.run_main(family.main, str(self.db), *args)

    def person_row(self, pid: int) -> tuple:
        return self.query(f"SELECT ParentID, SpouseID FROM PersonTable WHERE PersonID = {pid}")[0]

    def test_get(self):
        code, out = self.run_family("get", "1")
        self.assertEqual(code, 0)
        self.assertIn("F1  father P1 John Smith  mother P2 Mary Smith  (ChildID 3", out)
        self.assertIn("child 1: P3 Tom Smith", out)
        self.assertIn("child 2: P6 Jill Smith", out)
        self.assertIn("F1", self.run_family("get", "--person", "6")[1])
        self.assertEqual(self.run_family("get", "--person", "4")[0], 1)
        self.assertEqual(self.run_family("get", "99")[0], 1)

    def test_create(self):
        before = self.db.read_bytes()
        args = ("create", "--father", "3", "--mother", "4", "--child", "5", "--set", "Note=n")
        self.assertEqual((self.run_family(*args)[0], self.db.read_bytes()), (0, before))
        code, out = self.run_family(*args, "--apply")
        self.assertEqual(code, 0)
        self.assertIn("Applied: family F3.", out)
        self.assertEqual(self.query("SELECT FatherID, MotherID, ChildID, HusbOrder, WifeOrder, Note FROM FamilyTable"
                                    " WHERE FamilyID = 3"), [(3, 4, 0, 0, 0, "n")])
        self.assertEqual(self.query("SELECT ChildID, ChildOrder FROM ChildTable WHERE FamilyID = 3"), [(5, 1)])
        self.assertEqual(self.person_row(3), (1, 3))   # already a child of F1, now a partner of F3
        self.assertEqual(self.person_row(4), (0, 3))
        self.assertEqual(self.person_row(5), (3, 2))   # SpouseID of an existing family is kept

    def test_create_refusals(self):
        code, out = self.run_family("create", "--father", "1", "--mother", "2", "--child", "1", "--child", "99")
        self.assertEqual(code, 1)
        self.assertIn("F1 already has this father and mother", out)
        self.assertIn("P1 is also a partner of the family", out)
        self.assertIn("P99 not found", out)
        self.assertEqual(self.run_family("create")[0], 1)

    def test_edit_children_and_partners(self):
        code, out = self.run_family("edit", "1", "--remove-child", "3", "--add-child", "4", "--mother", "0",
                                    "--set", "Note=new", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.query("SELECT FatherID, MotherID, ChildID, Note FROM FamilyTable WHERE FamilyID = 1"),
                         [(1, 0, 0, "new")])
        self.assertEqual(self.query("SELECT ChildID, ChildOrder FROM ChildTable WHERE FamilyID = 1 ORDER BY RecID"),
                         [(6, 2), (4, 3)])
        self.assertEqual(self.person_row(3), (0, 0))
        self.assertEqual(self.person_row(2), (0, 0))
        self.assertEqual(self.person_row(4), (1, 0))
        self.assertEqual(self.person_row(1), (0, 1))

    def test_edit_replace_partner(self):
        code, _ = self.run_family("edit", "1", "--father", "3", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.person_row(1), (0, 0))
        self.assertEqual(self.person_row(3), (1, 1))

    def test_edit_refusals(self):
        code, out = self.run_family("edit", "1", "--add-child", "3", "--remove-child", "5", "--father", "0",
                                    "--mother", "0")
        self.assertEqual(code, 1)
        self.assertIn("P3 is already a child of F1", out)
        self.assertIn("P5 is not a child of F1", out)
        self.assertIn("no father and no mother", out)
        code, out = self.run_family("edit", "2", "--father", "1", "--mother", "2")
        self.assertIn("F1 already has this father and mother", out)
        self.assertEqual(self.run_family("edit", "99", "--set", "Note=x")[0], 1)
        self.assertEqual(self.run_family("edit", "1")[0], 1)

    def test_delete(self):
        code, _ = self.run_family("delete", "1", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.query("SELECT FamilyID FROM FamilyTable"), [(2,)])
        self.assertEqual(self.query("SELECT COUNT(*) FROM ChildTable"), [(0,)])
        for pid in (1, 2, 3, 6):
            self.assertEqual(self.person_row(pid), (0, 0))
        self.assertEqual(self.person_row(5), (0, 2))

    def test_delete_refused_when_used(self):
        import sqlite3
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO EventTable (EventID, EventType, OwnerType, OwnerID) VALUES (1, 300, 1, 1)")
        conn.commit()
        conn.close()
        code, out = self.run_family("delete", "1", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("still used: {'events': 1}", out)
        self.assertEqual(self.run_family("delete", "99")[0], 1)


if __name__ == "__main__":
    unittest.main()
