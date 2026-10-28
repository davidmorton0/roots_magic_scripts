import sqlite3
import unittest

from support import ScriptTestCase

import evaluate_citation
import rmutils

TYPES = """# Test

## Citation forms

| Form | Name | Fields | Transcription | Last line |
|---|---|---|---|---|
| Index entry | `* Register - UK - TestBMD` | SpecificItem=entry for *, vol. *, p. *; Citing=Test Office, * registered in * | index | `https://test.example/cite=*` |
| Certificate | `Birth Certificate - UK` | Page=*, born *; registered *; certificate *\\|*, born *; certificate * | labels | - |

## Not yet defined
"""
FIELD_DEFS = ("<Root><Fields>"
              "<Field><FieldName>URL</FieldName><CitationField>False</CitationField></Field>"
              "<Field><FieldName>AccessDate</FieldName><CitationField>True</CitationField></Field>"
              "<Field><FieldName>SpecificItem</FieldName><CitationField>True</CitationField></Field>"
              "<Field><FieldName>Citing</FieldName><CitationField>True</CitationField></Field>"
              "</Fields></Root>")
GOOD_TEXT = "Births Mar 1886  (>99%)\r\nDOE\tJane\tTestham\t2a\t602\r\nhttps://test.example/cite=abc"


def web(access: str, item: str, citing: str) -> tuple[bytes, str]:
    fields = {"AccessDate": access, "SpecificItem": item, "Citing": citing}
    return rmutils.fields_blob(fields, declaration=False), "; ".join(fields.values())


class EvaluateCitationMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.types = self.tmp / "source_types.md"
        self.types.write_text(TYPES, encoding="utf-8")
        conn = sqlite3.connect(self.db)
        conn.executescript(f"""
            CREATE TABLE SourceTemplateTable (TemplateID INTEGER PRIMARY KEY, FieldDefs BLOB);
            INSERT INTO SourceTemplateTable VALUES (6, '{FIELD_DEFS}');
            CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, Name TEXT, TemplateID INTEGER);
            INSERT INTO SourceTable VALUES (1, 'Birth Register - UK - TestBMD', 6), (2, 'Birth Certificate - UK', 0),
                (3, 'Misc notes', 0);
            CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER, Fields BLOB,
                CitationName TEXT, ActualText TEXT);
            CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER, OwnerType INTEGER,
                OwnerID INTEGER);
            CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, OwnerType INTEGER, OwnerID INTEGER);
            CREATE TABLE FamilyTable (FamilyID INTEGER PRIMARY KEY, FatherID INTEGER, MotherID INTEGER);
            CREATE TABLE MultimediaTable (MediaID INTEGER PRIMARY KEY, MediaPath TEXT, MediaFile TEXT);
            CREATE TABLE MediaLinkTable (LinkID INTEGER PRIMARY KEY, MediaID INTEGER, OwnerType INTEGER,
                OwnerID INTEGER);
            INSERT INTO EventTable VALUES (20, 0, 5), (21, 0, 5), (22, 1, 30);
            INSERT INTO FamilyTable VALUES (30, 5, 6);
            INSERT INTO MultimediaTable VALUES (1, 'H:\\Records', 'a.tif'), (2, 'H:\\Records', 'b.tif');
        """)
        good, good_name = web("3 June 2021", "entry for Jane Doe, Testham, vol. 2a, p. 602",
                              "Test Office, Births registered in January, February, and March 1886")
        empty_access, empty_name = web("", "entry for Ann Doe, Testham, vol. 2a, p. 603",
                                       "Test Office, Births registered in April, May, and June 1886")
        bad, _ = web("2021-06-03", "Ann Doe at Testham", "elsewhere")
        rows = [
            (10, 1, good, good_name, GOOD_TEXT),
            (11, 1, empty_access, empty_name, "Births Jun 1886\nDOE Ann Testham 2a 603"),
            (12, 1, bad, "old name", "Name:\tAnn"),
            (13, 1, good, good_name, GOOD_TEXT),
            (14, 2, rmutils.fields_blob({"Page": "Jane Doe, born 1 May 1886; certificate X1"}, declaration=False),
             "Jane Doe, born 1 May 1886; certificate X1", "District: Testham\r\nNo: 1"),
            (15, 3, rmutils.fields_blob({"Page": "a note"}, declaration=False), "a note", ""),
        ]
        conn.executemany("INSERT INTO CitationTable VALUES (?, ?, ?, ?, ?)", rows)
        conn.executemany("INSERT INTO CitationLinkTable (CitationID, OwnerType, OwnerID) VALUES (?, ?, ?)",
                         [(10, 2, 20), (11, 2, 21), (12, 1, 30), (13, 0, 5), (14, 2, 20)])
        conn.executemany("INSERT INTO MediaLinkTable (MediaID, OwnerType, OwnerID) VALUES (?, 4, ?)",
                         [(1, 10), (2, 11), (1, 13)])
        conn.commit()
        conn.close()

    def run_evaluate(self, *args: str) -> tuple[int, str]:
        return self.run_main(evaluate_citation.main, str(self.db), "--types", str(self.types), *args)

    def details(self) -> str:
        return self.output_path("evaluate_citation", "citations").read_text(encoding="utf-8")

    def test_clean_citations(self):
        code, out = self.run_evaluate("--citation", "14")
        self.assertEqual(code, 0)
        self.assertIn("S2 'Birth Certificate - UK' [Certificate]: 1 citations, 0 flagged", out)
        self.assertIn("C14  S2 'Birth Certificate - UK'  form: Certificate", self.details())

    def test_flags(self):
        code, out = self.run_evaluate("--source", "1")
        self.assertEqual(code, 0)
        self.assertIn("4 citations, 4 flagged", out)
        details = self.details()
        for line in (
                "G16 AccessDate empty; 1 scan(s)",
                "C2 transcription lines end with LF only",
                "G10 not in the index layout",
                "LAST last line 'DOE Ann Testham 2a 603'",
                "C3 AccessDate '2021-06-03' not written as '7 August 2020'",
                "FORM SpecificItem 'Ann Doe at Testham' does not have the shape 'entry for *, vol. *, p. *'",
                "FORM Citing 'elsewhere'",
                "C1 CitationName 'old name'; fields give '2021-06-03; Ann Doe at Testham; elsewhere'",
                "G10 a tab after a label",
                "G11 same entry as C13",
                "G12 shares a scan and a person with C13",
        ):
            self.assertIn(line, details)
        self.assertNotIn("C1 CitationName '; entry for Ann Doe", details)

    def test_free_form_without_form(self):
        code, out = self.run_evaluate("--source", "3")
        self.assertIn("S3 'Misc notes' [no form]: 1 citations, 1 flagged; G10 1, UNUSED 1", out)
        self.assertIn("! G10 transcription is empty", self.details())

    def test_all_and_missing(self):
        code, out = self.run_evaluate("--all")
        self.assertEqual(code, 0)
        self.assertIn("S1 'Birth Register - UK - TestBMD'", out)
        code, out = self.run_evaluate("--citation", "99")
        self.assertEqual(code, 1)
        self.assertIn("Not found: C99", out)

    def test_skill_table_parses(self):
        forms = evaluate_citation.load_forms(evaluate_citation.TYPES_FILE)
        self.assertGreater(len(forms), 10)
        death = next(f for f in forms if f.name == "UK death certificate")
        self.assertTrue(death.fields["Page"][0].fullmatch(
            "A B, died 1 May 1900, Testham; registered June quarter 1900, Testham district, Testham sub-district,"
            " entry 5; certificate DYB 1, issued 2 May 2006, General Register Office, Southport"))


if __name__ == "__main__":
    unittest.main()
