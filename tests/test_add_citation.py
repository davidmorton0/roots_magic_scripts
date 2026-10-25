import sqlite3
import unittest

from support import ScriptTestCase

import add_citation
import rmutils

FIELD_DEFS = ("<Root><Fields>"
              "<Field><FieldName>URL</FieldName><CitationField>False</CitationField></Field>"
              "<Field><FieldName>AccessDate</FieldName><CitationField>True</CitationField></Field>"
              "<Field><FieldName>SpecificItem</FieldName><CitationField>True</CitationField></Field>"
              "<Field><FieldName>Citing</FieldName><CitationField>True</CitationField></Field>"
              "</Fields></Root>")
SETUP_SQL = f"""
CREATE TABLE SourceTemplateTable (TemplateID INTEGER PRIMARY KEY, FieldDefs BLOB);
INSERT INTO SourceTemplateTable VALUES (6, '{FIELD_DEFS}');
CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, Name TEXT, TemplateID INTEGER);
INSERT INTO SourceTable VALUES (1, 'Census - England 1881 - Ancestry', 6), (2, 'Birth Certificate - UK', 0);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER, Comments TEXT, ActualText TEXT,
    RefNumber TEXT, Footnote TEXT, ShortFootnote TEXT, Bibliography TEXT, Fields BLOB, UTCModDate FLOAT,
    CitationName TEXT);
INSERT INTO CitationTable VALUES (5, 1, '', '', '', '', '', '', NULL, 1.0, '1 May 2020; household of Ann Old; RG11');
CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER, OwnerType INTEGER, OwnerID INTEGER,
    SortOrder INTEGER, Quality TEXT, IsPrivate INTEGER, Flags INTEGER, UTCModDate FLOAT);
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY);
CREATE TABLE FamilyTable (FamilyID INTEGER PRIMARY KEY);
INSERT INTO EventTable VALUES (20), (21);
INSERT INTO FamilyTable VALUES (30);
"""
FIELDS = ["--field", "AccessDate=3 June 2021", "--field", "SpecificItem=household of Tom Test, 1 Hill St",
          "--field", "Citing=RG11, piece 1, folio 2, page 3"]


class AddCitationMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.commit()
        conn.close()
        self.text = self.tmp / "text.txt"
        self.text.write_text("Name: Tom Test\nAge: 30\n", encoding="utf-8")

    def query(self, sql: str) -> list[tuple]:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute(sql).fetchall()
        finally:
            conn.close()

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(add_citation.main, str(self.db), "--source", "1", *FIELDS,
                                  "--link", "event:20:PDX")
        self.assertEqual(code, 0)
        self.assertIn("CitationName: 3 June 2021; household of Tom Test, 1 Hill St; RG11, piece 1, folio 2, page 3", out)
        self.assertIn("link -> event 20 PDX", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply_adds_citation_and_links(self):
        code, out = self.run_main(add_citation.main, str(self.db), "--source", "1", *FIELDS,
                                  "--text-file", str(self.text), "--comments", "a note",
                                  "--link", "event:20:PDX", "--link", "family:30:PIX", "--apply")
        self.assertEqual(code, 0)
        self.assertIn("Applied: citation C6.", out)
        row = self.query("SELECT SourceID, Comments, ActualText, Fields, CitationName FROM CitationTable"
                         " WHERE CitationID = 6")[0]
        self.assertEqual(row[:3], (1, "a note", "Name: Tom Test\r\nAge: 30"))
        self.assertEqual(rmutils.read_fields(row[3]), {"AccessDate": "3 June 2021",
                                                       "SpecificItem": "household of Tom Test, 1 Hill St",
                                                       "Citing": "RG11, piece 1, folio 2, page 3"})
        self.assertFalse(bytes(row[3]).startswith(b"<?xml"))
        self.assertEqual(self.query("SELECT CitationID, OwnerType, OwnerID, Quality FROM CitationLinkTable"),
                         [(6, 2, 20, "PDX"), (6, 1, 30, "PIX")])

    def test_free_form_takes_page(self):
        code, _ = self.run_main(add_citation.main, str(self.db), "--source", "2", "--field",
                                "Page=Tom Test, born 1 May 1880", "--link", "event:21:PDO", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.query("SELECT CitationName FROM CitationTable WHERE CitationID = 6"),
                         [("Tom Test, born 1 May 1880",)])

    def test_refusals(self):
        code, out = self.run_main(add_citation.main, str(self.db), "--source", "1", "--field", "Page=x",
                                  "--link", "event:99:PD", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("'Page' is not a citation field of template 6", out)
        self.assertIn("quality 'PD' is not three characters", out)
        self.assertIn("event 99 not found", out)
        code, out = self.run_main(add_citation.main, str(self.db), "--source", "1", "--field", "AccessDate=1 May 2020",
                                  "--field", "SpecificItem=household of Ann Old", "--field", "Citing=RG11", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("C5 of S1 already has this CitationName", out)
        self.assertEqual(self.query("SELECT COUNT(*) FROM CitationTable"), [(1,)])


if __name__ == "__main__":
    unittest.main()
