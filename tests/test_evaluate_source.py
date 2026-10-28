import sqlite3
import unittest

from support import ScriptTestCase

import evaluate_source
import rmutils

TYPES = """# Source types

## Source types

| Type | Name | Template | Required | Fixed | Text |
|---|---|---|---|---|---|
| Test index | `* Register - UK - TestBMD` | 6 | WebsiteCreator | Descriptor=database\\|database with images; WebsiteTitle=TestBMD; URL=https://test.example | - |
| Oral history | `Oral history - *` | 0 | | Footnote={1}, oral history | What {1} told the compiler |
| Own photographs | `* - Photographs` | 10005 | Collection | | - |
| Photo of unknown origin | `* - Photographs or * - Image` | 0 | | | - |

## Not yet defined
"""


def blob(fields: dict, declaration: bool = False) -> bytes:
    return rmutils.fields_blob(fields, declaration=declaration)


WEB = {"DatabaseCreator": "", "DatabaseTitle": "Birth Index", "Descriptor": "database with images",
       "WebsiteCreator": "Test Org", "WebsiteTitle": "TestBMD", "URL": "https://test.example"}


class EvaluateSourceMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.types = self.tmp / "source_types.md"
        self.types.write_text(TYPES, encoding="utf-8")
        conn = sqlite3.connect(self.db)
        conn.create_collation("RMNOCASE", rmutils.rmnocase)
        conn.executescript("""
            CREATE TABLE SourceTemplateTable (TemplateID INTEGER PRIMARY KEY, Name TEXT, FieldDefs BLOB);
            INSERT INTO SourceTemplateTable VALUES (6, 'Complex Website', ''), (10005, 'Photo', ''),
                (10013, 'Newspapers', '');
            CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, Name TEXT COLLATE RMNOCASE, TemplateID INTEGER,
                Fields BLOB, ActualText TEXT, Comments TEXT);
            CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER);
            CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER);
            CREATE TABLE MultimediaTable (MediaID INTEGER PRIMARY KEY, MediaPath TEXT, MediaFile TEXT);
            CREATE TABLE MediaLinkTable (LinkID INTEGER PRIMARY KEY, MediaID INTEGER, OwnerType INTEGER,
                OwnerID INTEGER);
        """)
        rows = [
            (1, "Birth Register - UK - TestBMD", 6, blob(WEB), "Index pages viewed as images", ""),
            (2, "Death Register - UK - TestBMD", 6,
             blob({**WEB, "DatabaseTitle": "", "DatabaseCreator": "X", "URL": "http://old", "WebsiteCreator": ""}),
             "See https://test.example", "pasted text"),
            (3, "Oral history - Ann Test", 0,
             blob({"Footnote": "Ann Test, oral history", "ShortFootnote": "s", "Bibliography": "b"}),
             "What Ann Test told the compiler", ""),
            (4, "Oral history - Bob Test", 0, blob({"Footnote": "wrong", "ShortFootnote": "s", "Bibliography": "b"}),
             "other text", ""),
            (5, "Newspaper -  Daily Test ", 10013, blob({"NameofPaper": "Daily Test"}, declaration=True), "", ""),
            (6, "Newspaper - Daily Test", 10013, blob({"NameofPaper": "Daily Test"}, declaration=True), "", ""),
            (7, "Graves - England - Testham - Photographs", 10005, blob({"Collection": "c"}), "Own photos", ""),
            (8, "Graves - England - Testham - Image", 6, blob({**WEB, "DatabaseTitle": "Graves"}), "text", ""),
            (9, "Notes - Nowhere - Someone", 0, blob({"Footnote": "f"}), "text", ""),
        ]
        conn.executemany("INSERT INTO SourceTable VALUES (?, ?, ?, ?, ?, ?)", rows)
        conn.executemany("INSERT INTO CitationTable VALUES (?, ?)",
                         [(10, 1), (11, 2), (12, 3), (13, 4), (14, 5), (15, 7), (16, 8), (17, 9)])
        conn.execute("INSERT INTO CitationLinkTable VALUES (1, 10)")
        conn.execute("INSERT INTO MultimediaTable VALUES (1, 'H:\\My Drive\\Records\\Newspaper\\Test', 'a.jpg')")
        conn.execute("INSERT INTO MediaLinkTable VALUES (1, 1, 4, 16)")
        conn.commit()
        conn.close()

    def run_evaluate(self, *args: str) -> tuple[int, str]:
        return self.run_main(evaluate_source.main, str(self.db), "--types", str(self.types), *args)

    def details(self) -> str:
        return self.output_path("evaluate_source", "sources").read_text(encoding="utf-8")

    def test_clean_source_has_no_flags(self):
        code, out = self.run_evaluate("--source", "1", "--source", "3")
        self.assertEqual(code, 0)
        self.assertIn("S1 'Birth Register - UK - TestBMD' [Test index]: 0 flags", out)
        self.assertIn("S3 'Oral history - Ann Test' [Oral history]: 0 flags", out)
        self.assertIn("citations 1, links 1, scans 0", self.details())

    def test_type_fields_text_and_comments(self):
        code, out = self.run_evaluate("--source", "2", "--source", "4")
        self.assertEqual(code, 0)
        for line in ("L2 DatabaseTitle is empty", "L2 WebsiteCreator is empty", "L2 DatabaseCreator 'X' is filled",
                     "FIXED URL 'http://old'; expected 'https://test.example'", "G4 source text holds a URL",
                     "G4 comments not empty", "FIXED Footnote 'wrong'; expected 'Bob Test, oral history'",
                     "TEXT source text 'other text'; expected 'What Bob Test told the compiler'"):
            self.assertIn(line, out)
        self.assertNotIn("FIXED Descriptor", out)

    def test_no_type_name_template_layout_and_duplicates(self):
        code, out = self.run_evaluate("--source", "5", "--source", "9")
        for line in ("S5 'Newspaper -  Daily Test ' [no type]", "TYPE no source type",
                     "G2 name has 2 part(s)", "G1 template 10013 (Newspapers) is neither 0",
                     "G2 name has spaces at either end or two together",
                     "L1 Fields saved with a byte-order mark", "G4 source text is empty",
                     "G3 same name or database as S6 'Newspaper - Daily Test'",
                     "G2 country part 'Nowhere' not a known country", "L2 ShortFootnote is empty"):
            self.assertIn(line, out)

    def test_type_chosen_by_template_and_wrong_template(self):
        code, out = self.run_evaluate("--source", "7", "--source", "8")
        self.assertIn("S7 'Graves - England - Testham - Photographs' [Own photographs]: 0 flags", out)
        self.assertIn("G1 template 6 (Complex Website); type 'Photo of unknown origin' has 0", out)
        self.assertIn("G18 citation scans in a Newspaper folder", out)

    def test_all_counts_and_unused(self):
        code, out = self.run_evaluate("--all")
        self.assertEqual(code, 0)
        self.assertIn("9 sources; 6 with flags", out)
        self.assertIn("L3", out)
        self.assertIn("S6  'Newspaper - Daily Test'", self.details())
        self.assertIn("! L3 no citations", self.details())

    def test_missing_source(self):
        code, out = self.run_evaluate("--source", "99")
        self.assertEqual(code, 1)
        self.assertIn("Sources not found: S99", out)

    def test_skill_table_parses(self):
        types = evaluate_source.load_types(evaluate_source.TYPES_FILE)
        self.assertGreater(len(types), 10)
        self.assertEqual(types[0].template, 6)


if __name__ == "__main__":
    unittest.main()
