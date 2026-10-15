import sqlite3
import unittest

from support import ScriptTestCase

import split_source
from rmutils import read_fields

FIELDS = (
    "<Root><Fields><Field><Name>Repository</Name><Value>Birth Index</Value></Field>"
    "<Field><Name>RepositoryLoc</Name><Value>Ancestry</Value></Field></Fields></Root>"
).encode("utf-8")

SETUP_SQL = """
CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, Name TEXT, RefNumber TEXT,
    ActualText TEXT, Comments TEXT, IsPrivate INTEGER, TemplateID INTEGER, Fields BLOB,
    UTCModDate FLOAT);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER,
    CitationName TEXT, ActualText TEXT, UTCModDate FLOAT);
INSERT INTO CitationTable VALUES
    (10, 590, 'Death entry', 'Name: X | Death Age: 70', 1.0),
    (11, 590, 'Birth entry', 'Births Mar 1904', 1.0),
    (12, 590, 'Death, no text', '', 1.0);
"""


class SplitSourceMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.executemany(
            "INSERT INTO SourceTable VALUES (?, ?, '', 'ancestry.co.uk', 'notes', 0, ?, ?, 1.0)",
            [(590, "Birth - Ancestry", 10003, FIELDS), (704, "Death - Ancestry", 10003, FIELDS),
             (800, "Other template", 6, FIELDS)],
        )
        conn.commit()
        conn.close()

    def query(self, sql: str) -> list[tuple]:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute(sql).fetchall()
        finally:
            conn.close()

    def test_dry_run_lists_and_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(
            split_source.main, str(self.db), "--from", "590", "--match", "Death Age:",
            "--include", "12", "--to", "704",
        )
        self.assertEqual(code, 0)
        self.assertIn("Citations to move from S590: 2\n   C10 Death entry\n   C12 Death, no text\n", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply_moves_into_existing_source(self):
        code, out = self.run_main(
            split_source.main, str(self.db), "--from", "590", "--match", "Death Age:",
            "--include", "12", "--to", "704", "--apply",
        )
        self.assertEqual(code, 0)
        self.assertEqual(
            self.query("SELECT CitationID, SourceID FROM CitationTable ORDER BY CitationID"),
            [(10, 704), (11, 590), (12, 704)],
        )

    def test_apply_creates_new_source(self):
        code, out = self.run_main(
            split_source.main, str(self.db), "--from", "590", "--match", "Death Age:",
            "--name", "Death - Ancestry 2", "--field", "Repository=Death Index",
            "--comments", "", "--apply",
        )
        self.assertEqual(code, 0)
        (new_id, text, comments, template, fields), = self.query(
            "SELECT SourceID, ActualText, Comments, TemplateID, Fields FROM SourceTable"
            " WHERE Name = 'Death - Ancestry 2'"
        )
        self.assertEqual((text, comments, template), ("ancestry.co.uk", "", 10003))
        self.assertEqual(read_fields(fields), {"Repository": "Death Index", "RepositoryLoc": "Ancestry"})
        self.assertEqual(self.query("SELECT SourceID FROM CitationTable WHERE CitationID = 10"), [(new_id,)])

    def test_refuses_target_with_other_template(self):
        code, out = self.run_main(
            split_source.main, str(self.db), "--from", "590", "--match", "Death Age:", "--to", "800",
        )
        self.assertEqual(code, 1)
        self.assertIn("uses template 6, not 10003", out)

    def test_refuses_existing_name(self):
        code, out = self.run_main(
            split_source.main, str(self.db), "--from", "590", "--match", "Death Age:",
            "--name", "death - ancestry",
        )
        self.assertEqual(code, 1)
        self.assertIn("already exists", out)


if __name__ == "__main__":
    unittest.main()
