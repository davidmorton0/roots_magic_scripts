import sqlite3
import unittest

from support import ScriptTestCase

import change_citation_source
from rmutils import fields_blob, read_fields

DEFS = ("<Root><Fields>"
        "<Field><FieldName>AccessDate</FieldName><CitationField>True</CitationField></Field>"
        "<Field><FieldName>SpecificItem</FieldName><CitationField>True</CitationField></Field>"
        "<Field><FieldName>Citing</FieldName><CitationField>True</CitationField></Field>"
        "</Fields></Root>").encode()
SETUP_SQL = """
CREATE TABLE SourceTemplateTable (TemplateID INTEGER PRIMARY KEY, FieldDefs BLOB);
CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, Name TEXT, TemplateID INTEGER);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER, CitationName TEXT,
    ActualText TEXT, Fields BLOB, UTCModDate FLOAT);
CREATE TABLE MultimediaTable (MediaID INTEGER PRIMARY KEY, Description TEXT, UTCModDate FLOAT);
CREATE TABLE MediaLinkTable (LinkID INTEGER PRIMARY KEY, MediaID INTEGER, OwnerType INTEGER, OwnerID INTEGER);
INSERT INTO SourceTable VALUES (583, 'FreeBMD', 6), (590, 'Ancestry', 6), (700, 'Other', 99);
INSERT INTO MultimediaTable VALUES (1, 'old description', 1.0);
INSERT INTO MediaLinkTable (MediaID, OwnerType, OwnerID) VALUES (1, 4, 10);
"""
FIELDS = {"AccessDate": "8 November 2020", "SpecificItem": "entry for Walter B Roe (Ancestry db)",
          "Citing": "GRO 1934"}
ARGS = ["--citation", "10", "--to-source", "583", "--specific-item", "entry for Walter B. Roe",
        "--text", "Births Dec 1934\nRoe\tWalter B.", "--media", "1", "--description", "new description"]


class ChangeCitationSourceMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.execute("INSERT INTO SourceTemplateTable VALUES (6, ?)", (DEFS,))
        conn.execute("INSERT INTO CitationTable VALUES (10, 590, 'old', 'Name: William', ?, 1.0)",
                     (fields_blob(FIELDS, declaration=False),))
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
        code, out = self.run_main(change_citation_source.main, str(self.db), *ARGS)
        self.assertEqual(code, 0)
        self.assertIn("C10: source S590 -> S583 'FreeBMD'", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply(self):
        code, _ = self.run_main(change_citation_source.main, str(self.db), *ARGS, "--apply")
        self.assertEqual(code, 0)
        sid, name, text, blob = self.query("SELECT SourceID, CitationName, ActualText, Fields FROM CitationTable")[0]
        self.assertEqual((sid, text), (583, "Births Dec 1934\nRoe\tWalter B."))
        self.assertEqual(read_fields(blob)["SpecificItem"], "entry for Walter B. Roe")
        self.assertEqual(name, "8 November 2020; entry for Walter B. Roe; GRO 1934")
        self.assertEqual(self.query("SELECT Description FROM MultimediaTable"), [("new description",)])

    def test_refuses_other_template(self):
        args = list(ARGS)
        args[3] = "700"
        code, out = self.run_main(change_citation_source.main, str(self.db), *args)
        self.assertEqual(code, 1)
        self.assertIn("uses template 99, not 6", out)


if __name__ == "__main__":
    unittest.main()
