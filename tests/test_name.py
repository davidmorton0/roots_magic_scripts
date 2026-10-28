import unittest

from support import ScriptTestCase

import name

BLANK = "0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0"
EXTRA = f"""
INSERT INTO PersonTable VALUES (1, 'U1', 0, 0, 0, {BLANK}, '', 1.0);
INSERT INTO NameTable (NameID, OwnerID, Surname, Given, Prefix, Suffix, Nickname, NameType, IsPrimary, BirthYear,
    SurnameMP, GivenMP) VALUES
    (1, 1, 'Smith', 'John', '', '', '', 0, 1, 1850, 'Smith', 'John'),
    (2, 1, 'Smyth', 'Johnny', '', '', 'Jack', 1, 0, 1850, 'Other', 'Johnny');
INSERT INTO CitationLinkTable VALUES (1, 7, 7, 2, 0, 'PIX', 0, 0, 1.0);
"""


class NameMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.use_full_schema(EXTRA)

    def run_name(self, *args: str) -> tuple[int, str]:
        return self.run_main(name.main, str(self.db), *args)

    def test_get(self):
        code, out = self.run_name("get", "--person", "1")
        self.assertEqual(code, 0)
        self.assertIn("N1: P1 John Smith (NameType 0, primary)", out)
        self.assertIn("N2: P1 Johnny Smyth nickname 'Jack' (NameType 1)", out)
        self.assertEqual(self.run_name("get", "2")[0], 0)
        self.assertEqual(self.run_name("get", "99")[0], 1)
        self.assertEqual(self.run_name("get", "--person", "9")[0], 1)

    def test_create(self):
        before = self.db.read_bytes()
        args = ("create", "--person", "1", "--given", "Joe", "--surname", "Smythe", "--nickname", "Joey")
        self.assertEqual((self.run_name(*args)[0], self.db.read_bytes()), (0, before))
        code, out = self.run_name(*args, "--apply")
        self.assertEqual(code, 0)
        self.assertIn("Applied: name N3.", out)
        self.assertEqual(self.query("SELECT OwnerID, Given, Surname, Nickname, NameType, Date, SortDate, IsPrimary,"
                                    " BirthYear, GivenMP, SurnameMP FROM NameTable WHERE NameID = 3"),
                         [(1, "Joe", "Smythe", "Joey", 1, ".", 9223372036854775807, 0, 1850, "Joe", "Smythe")])

    def test_create_refusals(self):
        code, out = self.run_name("create", "--person", "1", "--given", "JOHNNY", "--surname", "smyth", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("P1 already has the name JOHNNY smyth", out)
        code, out = self.run_name("create", "--person", "9", "--given", "A", "--surname", "B", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("P9 not found", out)

    def test_edit_follows_mp_only_when_equal(self):
        code, _ = self.run_name("edit", "2", "--given", "Jon", "--surname", "Smythe", "--type", "2", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.query("SELECT Given, Surname, GivenMP, SurnameMP, NameType FROM NameTable"
                                    " WHERE NameID = 2"), [("Jon", "Smythe", "Jon", "Other", 2)])
        self.assertEqual(self.run_name("edit", "99", "--note", "x")[0], 1)
        self.assertEqual(self.run_name("edit", "2")[0], 1)

    def test_delete(self):
        code, out = self.run_name("delete", "1", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("primary name cannot be deleted", out)
        code, out = self.run_name("delete", "2", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("1 citation links; give --with-links", out)
        code, _ = self.run_name("delete", "2", "--with-links", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.query("SELECT NameID FROM NameTable"), [(1,)])
        self.assertEqual(self.query("SELECT COUNT(*) FROM CitationLinkTable"), [(0,)])


if __name__ == "__main__":
    unittest.main()
