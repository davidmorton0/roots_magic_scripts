import sqlite3
import unittest

from support import ScriptTestCase

import citation
import rmutils

FIELD_DEFS = ("<Root><Fields>"
              "<Field><FieldName>URL</FieldName><CitationField>False</CitationField></Field>"
              "<Field><FieldName>AccessDate</FieldName><CitationField>True</CitationField></Field>"
              "<Field><FieldName>SpecificItem</FieldName><CitationField>True</CitationField></Field>"
              "<Field><FieldName>Citing</FieldName><CitationField>True</CitationField></Field>"
              "</Fields></Root>")
OLD_FIELDS = (b"<Root><Fields><Field><Name>AccessDate</Name><Value>1 May 2020</Value></Field>"
              b"<Field><Name>SpecificItem</Name><Value>household of Ann Old</Value></Field>"
              b"<Field><Name>Citing</Name><Value>RG11</Value></Field></Fields></Root>")
SETUP_SQL = f"""
CREATE TABLE SourceTemplateTable (TemplateID INTEGER PRIMARY KEY, FieldDefs BLOB);
INSERT INTO SourceTemplateTable VALUES (6, '{FIELD_DEFS}');
CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, Name TEXT, TemplateID INTEGER);
INSERT INTO SourceTable VALUES (1, 'Census - England 1881 - Ancestry', 6), (2, 'Birth Certificate - UK', 0);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER, Comments TEXT, ActualText TEXT,
    RefNumber TEXT, Footnote TEXT, ShortFootnote TEXT, Bibliography TEXT, Fields BLOB, UTCModDate FLOAT,
    CitationName TEXT);
CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER, OwnerType INTEGER, OwnerID INTEGER,
    SortOrder INTEGER, Quality TEXT, IsPrivate INTEGER, Flags INTEGER, UTCModDate FLOAT);
CREATE TABLE MultimediaTable (MediaID INTEGER PRIMARY KEY, MediaPath TEXT, MediaFile TEXT);
CREATE TABLE MediaLinkTable (LinkID INTEGER PRIMARY KEY, MediaID INTEGER, OwnerType INTEGER, OwnerID INTEGER);
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY);
CREATE TABLE FamilyTable (FamilyID INTEGER PRIMARY KEY);
INSERT INTO EventTable VALUES (20), (21);
INSERT INTO FamilyTable VALUES (30);
INSERT INTO MultimediaTable VALUES (3, 'C:\\Records', 'scan.pdf');
"""
FIELDS = ["--field", "AccessDate=3 June 2021", "--field", "SpecificItem=household of Tom Test, 1 Hill St",
          "--field", "Citing=RG11, piece 1, folio 2, page 3"]


class CitationMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.execute("INSERT INTO CitationTable VALUES (5, 1, 'old note', 'text', '', '', '', '', ?, 1.0, ?)",
                     (OLD_FIELDS, "1 May 2020; household of Ann Old; RG11"))
        conn.execute("INSERT INTO CitationTable VALUES (6, 1, '', '', '', '', '', '', NULL, 1.0, 'other')")
        conn.execute("INSERT INTO CitationLinkTable VALUES (1, 5, 2, 20, 0, 'PDX', 0, 0, 1.0)")
        conn.execute("INSERT INTO MediaLinkTable VALUES (1, 3, 4, 6)")
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

    def run_citation(self, *args: str) -> tuple[int, str]:
        return self.run_main(citation.main, str(self.db), *args)

    def test_get_by_id_and_by_source(self):
        code, out = self.run_citation("get", "5", "6")
        self.assertEqual(code, 0)
        self.assertIn("C5  S1 'Census - England 1881 - Ancestry'", out)
        self.assertIn("field Citing: RG11", out)
        self.assertIn("link -> event 20 PDX", out)
        self.assertIn("scan M3: C:\\Records\\scan.pdf", out)
        code, out = self.run_citation("get", "--source", "1")
        self.assertEqual(code, 0)
        self.assertIn("C6  S1", out)
        self.assertEqual(self.run_citation("get", "99")[0], 1)

    def test_create_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_citation("create", "--source", "1", *FIELDS, "--link", "event:20:PDX")
        self.assertEqual(code, 0)
        self.assertIn("CitationName: 3 June 2021; household of Tom Test, 1 Hill St; RG11, piece 1, folio 2, page 3", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_create_apply(self):
        code, out = self.run_citation("create", "--source", "1", *FIELDS, "--text-file", str(self.text),
                                      "--set", "Comments=a note", "--link", "event:20:PDX",
                                      "--link", "family:30:PIX", "--apply")
        self.assertEqual(code, 0)
        self.assertIn("Applied: citation C7.", out)
        row = self.query("SELECT SourceID, Comments, ActualText, Fields, UTCModDate FROM CitationTable"
                         " WHERE CitationID = 7")[0]
        self.assertEqual(row[:3], (1, "a note", "Name: Tom Test\r\nAge: 30"))
        self.assertEqual(rmutils.read_fields(row[3])["Citing"], "RG11, piece 1, folio 2, page 3")
        self.assertFalse(bytes(row[3]).startswith(b"<?xml"))
        self.assertEqual(self.query("SELECT OwnerType, OwnerID, Quality FROM CitationLinkTable"
                                    " WHERE CitationID = 7"), [(2, 20, "PDX"), (1, 30, "PIX")])

    def test_create_name_keeps_empty_fields(self):
        code, out = self.run_citation("create", "--source", "1", "--field", "SpecificItem=household of Tom Test",
                                      "--field", "Citing=RG11", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.query("SELECT CitationName FROM CitationTable WHERE CitationID = 7"),
                         [("; household of Tom Test; RG11",)])

    def test_create_free_form_and_refusals(self):
        code, _ = self.run_citation("create", "--source", "2", "--field", "Page=Tom Test, born 1880", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.query("SELECT CitationName FROM CitationTable WHERE CitationID = 7"),
                         [("Tom Test, born 1880",)])
        code, out = self.run_citation("create", "--source", "1", "--field", "Page=x", "--set", "Bad=1",
                                      "--link", "event:99:PD", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("'Page' is not a citation field", out)
        self.assertIn("--set 'Bad' is not one of", out)
        self.assertIn("quality 'PD' is not three characters", out)
        self.assertIn("event 99 not found", out)
        self.assertEqual(self.query("SELECT COUNT(*) FROM CitationTable"), [(3,)])

    def test_edit_field_rebuilds_name(self):
        code, out = self.run_citation("edit", "5", "--field", "Citing=RG11, piece 9", "--set", "Comments=new note",
                                      "--text-file", str(self.text), "--apply")
        self.assertEqual(code, 0)
        row = self.query("SELECT Comments, ActualText, Fields, CitationName, UTCModDate FROM CitationTable"
                         " WHERE CitationID = 5")[0]
        self.assertEqual(row[:2], ("new note", "Name: Tom Test\r\nAge: 30"))
        self.assertEqual(rmutils.read_fields(row[2]), {"AccessDate": "1 May 2020",
                                                       "SpecificItem": "household of Ann Old",
                                                       "Citing": "RG11, piece 9"})
        self.assertEqual(row[3], "1 May 2020; household of Ann Old; RG11, piece 9")
        self.assertGreater(row[4], 1.0)

    def test_edit_dry_run_and_refusals(self):
        before = self.db.read_bytes()
        code, out = self.run_citation("edit", "5", "--set", "Comments=x")
        self.assertEqual(code, 0)
        self.assertIn("Comments: 'old note' -> 'x'", out)
        self.assertEqual(self.db.read_bytes(), before)
        code, out = self.run_citation("edit", "5", "--set", "SourceID=2", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("--set 'SourceID' is not one of", out)
        code, out = self.run_citation("edit", "5", "--field", "Nope=1", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("'Nope' is not a citation field", out)
        self.assertEqual(self.run_citation("edit", "99", "--set", "Comments=x")[0], 1)
        self.assertEqual(self.run_citation("edit", "5")[0], 1)

    def test_edit_refuses_duplicate_name(self):
        code, out = self.run_citation("edit", "6", "--field", "AccessDate=1 May 2020",
                                      "--field", "SpecificItem=household of Ann Old", "--field", "Citing=RG11",
                                      "--apply")
        self.assertEqual(code, 1)
        self.assertIn("C5 of S1 already has CitationName", out)

    def test_delete(self):
        code, out = self.run_citation("delete", "5", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("1 links; give --with-links", out)
        code, out = self.run_citation("delete", "6", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("1 scans are attached", out)
        before = self.db.read_bytes()
        code, _ = self.run_citation("delete", "5", "--with-links")
        self.assertEqual((code, self.db.read_bytes()), (0, before))
        code, out = self.run_citation("delete", "5", "--with-links", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.query("SELECT COUNT(*) FROM CitationTable WHERE CitationID = 5"), [(0,)])
        self.assertEqual(self.query("SELECT COUNT(*) FROM CitationLinkTable"), [(0,)])


if __name__ == "__main__":
    unittest.main()
