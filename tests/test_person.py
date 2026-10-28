import unittest

from support import ScriptTestCase

import person

BLANK = "0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0"
EXTRA = f"""
INSERT INTO PersonTable VALUES (1, 'U1', 0, 3, 4, {BLANK}, '', 1.0);
INSERT INTO PersonTable VALUES (2, 'U2', 1, 0, 0, {BLANK}, 'a note', 1.0);
INSERT INTO PersonTable VALUES (3, 'U3', 2, 0, 0, {BLANK}, '', 1.0);
INSERT INTO NameTable (NameID, OwnerID, Surname, Given, Prefix, Suffix, IsPrimary, NameType) VALUES
    (1, 1, 'Smith', 'John', '', '', 1, 0), (2, 1, 'Smyth', 'John', '', '', 0, 1),
    (3, 2, 'Brown', 'Mary', 'Dr', '', 1, 0), (4, 3, 'Jones', 'Ann', '', 'Jr', 1, 0);
INSERT INTO EventTable (EventID, EventType, OwnerType, OwnerID) VALUES (10, 1, 0, 1);
INSERT INTO FamilyTable (FamilyID, FatherID, MotherID) VALUES (4, 1, 0);
INSERT INTO ChildTable (RecID, ChildID, FamilyID) VALUES (1, 1, 3);
"""


class PersonMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.use_full_schema(EXTRA)

    def run_person(self, *args: str) -> tuple[int, str]:
        return self.run_main(person.main, str(self.db), *args)

    def test_get(self):
        code, out = self.run_person("get", "1", "2")
        self.assertEqual(code, 0)
        self.assertIn("P1  John Smith  (sex male, ParentID F3, SpouseID F4", out)
        self.assertIn("name N2: John Smyth (NameType 1)", out)
        self.assertIn("partner in F4", out)
        self.assertIn("child of F3", out)
        self.assertIn("P2  Dr Mary Brown", out)
        self.assertIn("Note: 'a note'", out)
        code, out = self.run_person("get", "--name", "smyth")
        self.assertIn("P1  John Smith", out)
        self.assertEqual(self.run_person("get", "99")[0], 1)
        self.assertEqual(self.run_person("get", "--name", "zzz")[0], 1)

    def test_create(self):
        before = self.db.read_bytes()
        args = ("create", "--given", "Jane", "--surname", "Doe", "--sex", "female", "--note", "n")
        code, out = self.run_person(*args)
        self.assertEqual((code, self.db.read_bytes()), (0, before))
        self.assertIn("Dry run", out)
        code, out = self.run_person(*args, "--apply")
        self.assertEqual(code, 0)
        self.assertIn("Applied: person P4.", out)
        row = self.query("SELECT Sex, ParentID, SpouseID, Living, Note, length(UniqueID) FROM PersonTable"
                         " WHERE PersonID = 4")
        self.assertEqual(row, [(1, 0, 0, 0, "n", 36)])
        self.assertEqual(self.query("SELECT Given, Surname, NameType, Date, SortDate, IsPrimary, SurnameMP, GivenMP"
                                    " FROM NameTable WHERE OwnerID = 4"),
                         [("Jane", "Doe", 0, ".", 9223372036854775807, 1, "Doe", "Jane")])

    def test_create_reports_same_name(self):
        code, out = self.run_person("create", "--given", "John", "--surname", "SMITH", "--sex", "male")
        self.assertEqual(code, 0)
        self.assertIn("same name already used by P1", out)

    def test_edit(self):
        code, out = self.run_person("edit", "2", "--sex", "unknown", "--note", "new", "--living", "1")
        self.assertEqual(code, 0)
        self.assertIn("Sex: 1 -> 2", out)
        code, _ = self.run_person("edit", "2", "--sex", "unknown", "--note", "new", "--private", "1", "--apply")
        self.assertEqual(code, 0)
        row = self.query("SELECT Sex, Note, IsPrivate, UTCModDate FROM PersonTable WHERE PersonID = 2")[0]
        self.assertEqual(row[:3], (2, "new", 1))
        self.assertGreater(row[3], 1.0)
        self.assertEqual(self.run_person("edit", "99", "--note", "x")[0], 1)
        self.assertEqual(self.run_person("edit", "2")[0], 1)

    def test_delete(self):
        code, out = self.run_person("delete", "1", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("alternative names", out)
        self.assertIn("events", out)
        self.assertEqual(self.run_person("delete", "99")[0], 1)
        before = self.db.read_bytes()
        self.assertEqual((self.run_person("delete", "3")[0], self.db.read_bytes()), (0, before))
        code, _ = self.run_person("delete", "3", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.query("SELECT PersonID FROM PersonTable ORDER BY 1"), [(1,), (2,)])
        self.assertEqual(self.query("SELECT COUNT(*) FROM NameTable WHERE OwnerID = 3"), [(0,)])


if __name__ == "__main__":
    unittest.main()
