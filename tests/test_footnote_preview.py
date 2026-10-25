import sqlite3
import unittest

from support import ScriptTestCase

import footnote_preview
import rmutils

# Template 6 (Complex Website) sentences as stored in RootsMagic 12.
FOOTNOTE = ('<[DatabaseCreator], >"[DatabaseTitle]," <[Descriptor], ><[WebsiteCreator], ><i>[WebsiteTitle]</i>'
            ' ([URL]< : accessed [AccessDate]>)<, [SpecificItem]><; citing [Citing]>.')
SHORT = ('<[DatabaseCreator:Surname], ><?[SpecificItem:Abbrev]|"[DatabaseTitle:Abbrev]," [SpecificItem:Abbrev].'
         '|"[DatabaseTitle:Abbrev].">')
BIBLIOGRAPHY = ('<[DatabaseCreator:Reverse]. >"[DatabaseTitle]." <[Descriptor:Caps]. ><[WebsiteCreator]. >'
                '<i>[WebsiteTitle]</i>. [URL]< : [AccessDate:Year]><. Citing [Citing]>.')


class FootnotePreviewMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript("""
            CREATE TABLE SourceTemplateTable (TemplateID INTEGER PRIMARY KEY, Footnote TEXT, ShortFootnote TEXT,
                Bibliography TEXT);
            CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, TemplateID INTEGER, Fields BLOB);
            CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER, Fields BLOB);
        """)
        conn.execute("INSERT INTO SourceTemplateTable VALUES (6, ?, ?, ?)", (FOOTNOTE, SHORT, BIBLIOGRAPHY))
        blob = lambda d: rmutils.fields_blob(d, declaration=False)
        conn.execute("INSERT INTO SourceTable VALUES (1, 6, ?)", (blob({
            "DatabaseCreator": "", "DatabaseTitle": "Test Marriages, 1800-1900", "Descriptor": "database",
            "WebsiteCreator": "Example Inc", "WebsiteTitle": "Example", "URL": "https://example.org"}),))
        conn.execute("INSERT INTO SourceTable VALUES (2, 0, ?)", (blob({
            "Footnote": "England, test certificate (certified copy)",
            "ShortFootnote": "England, test certificate", "Bibliography": "England. Test Certificates."}),))
        conn.executemany("INSERT INTO CitationTable VALUES (?, ?, ?)", [
            (10, 1, blob({"AccessDate": "", "SpecificItem": "entry for John Smith", "Citing": "Testham register"})),
            (11, 1, blob({"AccessDate": "7 August 2020", "SpecificItem": "", "Citing": ""})),
            (12, 2, blob({"Page": "John Smith, born 1 May 1850"})),
        ])
        conn.commit()
        conn.close()

    def preview(self, cid: str) -> str:
        code, out = self.run_main(footnote_preview.main, str(self.db), cid)
        self.assertEqual(code, 0)
        return out

    def test_template_with_empty_access_date(self):
        out = self.preview("10")
        self.assertIn('Footnote: "Test Marriages, 1800-1900," database, Example Inc, *Example* (https://example.org),'
                      ' entry for John Smith; citing Testham register.', out)
        self.assertIn('Short footnote: "Test Marriages, 1800-1900," entry for John Smith.', out)
        self.assertIn('Bibliography: "Test Marriages, 1800-1900." Database. Example Inc. *Example*.'
                      ' https://example.org. Citing Testham register.', out)

    def test_optional_parts_and_conditional(self):
        out = self.preview("11")
        self.assertIn("(https://example.org : accessed 7 August 2020).", out)
        self.assertIn('Short footnote: "Test Marriages, 1800-1900."', out)
        self.assertIn("https://example.org : 2020.", out)

    def test_free_form(self):
        out = self.preview("12")
        self.assertIn("Footnote: England, test certificate (certified copy), John Smith, born 1 May 1850", out)
        self.assertIn("Short footnote: England, test certificate, John Smith, born 1 May 1850", out)
        self.assertIn("Bibliography: England. Test Certificates.", out)

    def test_unknown_citation(self):
        code, out = self.run_main(footnote_preview.main, str(self.db), "99")
        self.assertEqual(code, 1)
        self.assertIn("No citation C99", out)


if __name__ == "__main__":
    unittest.main()
