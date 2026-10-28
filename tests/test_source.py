import sqlite3
import unittest

from support import ScriptTestCase

import rmutils
import source

FIELD_DEFS = ("<Root><Fields>"
              "<Field><FieldName>Title</FieldName><CitationField>False</CitationField></Field>"
              "<Field><FieldName>URL</FieldName><CitationField>False</CitationField></Field>"
              "<Field><FieldName>Citing</FieldName><CitationField>True</CitationField></Field>"
              "</Fields></Root>")
SETUP_SQL = f"""
CREATE TABLE SourceTemplateTable (TemplateID INTEGER PRIMARY KEY, FieldDefs BLOB);
INSERT INTO SourceTemplateTable VALUES (6, '{FIELD_DEFS}');
CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, Name TEXT COLLATE RMNOCASE, RefNumber TEXT, ActualText TEXT,
    Comments TEXT, IsPrivate INTEGER, TemplateID INTEGER, Fields BLOB, UTCModDate FLOAT);
INSERT INTO SourceTable VALUES (1, 'Census 1881', '', 'old text', '', 0, 6,
    '<Root><Fields><Field><Name>Title</Name><Value>Census</Value></Field></Fields></Root>', 1.0);
INSERT INTO SourceTable VALUES (2, 'Unused', '', '', '', 0, 0, NULL, 1.0);
INSERT INTO SourceTable VALUES (3, 'Oral history', '', '', '', 0, 0, NULL, 1.0);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER);
INSERT INTO CitationTable VALUES (5, 1);
CREATE TABLE MediaLinkTable (LinkID INTEGER PRIMARY KEY, MediaID INTEGER, OwnerType INTEGER, OwnerID INTEGER);
CREATE TABLE TaskLinkTable (LinkID INTEGER PRIMARY KEY, TaskID INTEGER, OwnerType INTEGER, OwnerID INTEGER);
CREATE TABLE URLTable (LinkID INTEGER PRIMARY KEY, OwnerType INTEGER, OwnerID INTEGER);
CREATE TABLE AddressLinkTable (LinkID INTEGER PRIMARY KEY, OwnerType INTEGER, AddressID INTEGER, OwnerID INTEGER);
"""


class SourceMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.create_collation("RMNOCASE", rmutils.rmnocase)
        conn.executescript(SETUP_SQL)
        conn.commit()
        conn.close()

    def query(self, sql: str) -> list[tuple]:
        conn = sqlite3.connect(self.db)
        conn.create_collation("RMNOCASE", rmutils.rmnocase)
        try:
            return conn.execute(sql).fetchall()
        finally:
            conn.close()

    def run_source(self, *args: str) -> tuple[int, str]:
        return self.run_main(source.main, str(self.db), *args)

    def test_get(self):
        code, out = self.run_source("get", "1")
        self.assertEqual(code, 0)
        self.assertIn("S1  'Census 1881'  (template 6, IsPrivate 0)", out)
        self.assertIn("field Title: Census", out)
        self.assertIn("citations: 1", out)
        code, out = self.run_source("get", "--name", "ORAL")
        self.assertIn("S3  'Oral history'", out)
        self.assertEqual(self.run_source("get", "99")[0], 1)
        self.assertEqual(self.run_source("get", "--name", "nothing")[0], 1)

    def test_create(self):
        before = self.db.read_bytes()
        args = ("create", "--name", "New source", "--template", "6", "--field", "Title=T", "--field", "URL=u",
                "--set", "ActualText=about it")
        self.assertEqual((self.run_source(*args)[0], self.db.read_bytes()), (0, before))
        code, out = self.run_source(*args, "--apply")
        self.assertEqual(code, 0)
        self.assertIn("Applied: source S4.", out)
        row = self.query("SELECT Name, ActualText, IsPrivate, TemplateID, Fields FROM SourceTable"
                         " WHERE SourceID = 4")[0]
        self.assertEqual(row[:4], ("New source", "about it", 0, 6))
        self.assertEqual(rmutils.read_fields(row[4]), {"Title": "T", "URL": "u"})
        self.assertFalse(bytes(row[4]).startswith(b"<?xml"))

    def test_create_refusals(self):
        code, out = self.run_source("create", "--name", "census 1881", "--template", "6", "--field", "Citing=x",
                                    "--set", "Bad=1", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("S1 is already named 'census 1881'", out)
        self.assertIn("'Citing' is not a source field of template 6", out)
        self.assertIn("--set 'Bad' is not one of", out)
        code, out = self.run_source("create", "--name", "x", "--template", "77", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("template 77 not found", out)
        code, _ = self.run_source("create", "--name", "Free", "--field", "Footnote=f", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.query("SELECT COUNT(*) FROM SourceTable"), [(4,)])

    def test_edit(self):
        code, out = self.run_source("edit", "1", "--name", "Census 1881 - Ancestry", "--field", "URL=http://x",
                                    "--set", "Comments=a note", "--apply")
        self.assertEqual(code, 0)
        self.assertIn("rebuild indexes", out)
        row = self.query("SELECT Name, Comments, ActualText, Fields, UTCModDate FROM SourceTable"
                         " WHERE SourceID = 1")[0]
        self.assertEqual(row[:3], ("Census 1881 - Ancestry", "a note", "old text"))
        self.assertEqual(rmutils.read_fields(row[3]), {"Title": "Census", "URL": "http://x"})
        self.assertGreater(row[4], 1.0)

    def test_edit_refusals(self):
        before = self.db.read_bytes()
        code, out = self.run_source("edit", "1", "--set", "Comments=x")
        self.assertEqual((code, self.db.read_bytes()), (0, before))
        self.assertIn("Comments: '' -> 'x'", out)
        code, out = self.run_source("edit", "2", "--name", "CENSUS 1881", "--field", "Nope=1", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("S1 is already named 'CENSUS 1881'", out)
        self.assertIn("'Nope' is not a source field of template 0", out)
        self.assertEqual(self.run_source("edit", "99", "--name", "x")[0], 1)
        self.assertEqual(self.run_source("edit", "2")[0], 1)

    def test_delete(self):
        code, out = self.run_source("delete", "1", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("still used: {'citations': 1}", out)
        before = self.db.read_bytes()
        self.assertEqual((self.run_source("delete", "2")[0], self.db.read_bytes()), (0, before))
        code, _ = self.run_source("delete", "2", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.query("SELECT SourceID FROM SourceTable ORDER BY 1"), [(1,), (3,)])


if __name__ == "__main__":
    unittest.main()
