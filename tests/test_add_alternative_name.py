import sqlite3
import unittest

from support import ScriptTestCase

import add_alternative_name

SETUP_SQL = """
DROP TABLE NameTable;
CREATE TABLE NameTable (NameID INTEGER PRIMARY KEY, OwnerID INTEGER, Surname TEXT, Given TEXT, Prefix TEXT,
    Suffix TEXT, Nickname TEXT, NameType INTEGER, Date TEXT, SortDate INTEGER, IsPrimary INTEGER, IsPrivate INTEGER,
    Proof INTEGER, Sentence TEXT, Note TEXT, BirthYear INTEGER, DeathYear INTEGER, Display INTEGER, Language TEXT,
    UTCModDate FLOAT, SurnameMP TEXT, GivenMP TEXT, NicknameMP TEXT);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY);
CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER, OwnerType INTEGER,
    OwnerID INTEGER, SortOrder INTEGER, Quality TEXT, IsPrivate INTEGER, Flags INTEGER, UTCModDate FLOAT);
INSERT INTO NameTable (NameID, OwnerID, Surname, Given, IsPrimary, BirthYear) VALUES (1, 5, 'Smith', 'John Henry', 1, 1885);
INSERT INTO CitationTable VALUES (10);
"""
ARGS = ["--person", "5", "--given", "Henry John", "--surname", "Smith", "--citation", "10", "--quality", "PIX"]


class AddAlternativeNameMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.commit()
        conn.close()

    def query(self, sql) -> list[tuple]:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute(sql).fetchall()
        finally:
            conn.close()

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(add_alternative_name.main, str(self.db), *ARGS)
        self.assertEqual(code, 0)
        self.assertIn("P5 (John Henry Smith): add alternative name Henry John Smith, cited C10 PIX", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply_adds_name_and_link(self):
        code, _ = self.run_main(add_alternative_name.main, str(self.db), *ARGS, "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.query("SELECT OwnerID, Given, Surname, NameType, IsPrimary, BirthYear, GivenMP, SurnameMP"
                                    " FROM NameTable WHERE NameID = 2"),
                         [(5, "Henry John", "Smith", 1, 0, 1885, "Henry John", "Smith")])
        self.assertEqual(self.query("SELECT CitationID, OwnerType, OwnerID, Quality FROM CitationLinkTable"),
                         [(10, 7, 2, "PIX")])

    def test_refused(self):
        code, out = self.run_main(add_alternative_name.main, str(self.db), "--person", "5", "--given", "John Henry",
                                  "--surname", "Smith", "--citation", "99", "--quality", "PIX")
        self.assertEqual(code, 1)
        self.assertIn("C99 not found; P5 already has the name John Henry Smith", out)


if __name__ == "__main__":
    unittest.main()
