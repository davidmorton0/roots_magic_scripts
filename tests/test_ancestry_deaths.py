import sqlite3
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from support import ScriptTestCase

import ancestry_deaths
from rmutils import read_fields

EXAMPLE_CONFIG = Path(__file__).resolve().parent.parent / "config.example.toml"
FOLDER = "H:\\My Drive\\Records\\Deaths\\Britain\\Transcripts"
TEMPLATE_6_FIELDS = [
    "DatabaseCreator", "DatabaseTitle", "Descriptor", "WebsiteCreator",
    "WebsiteTitle", "URL", "AccessDate", "SpecificItem", "Citing",
]
REGISTER = ("Name: \tJohn Smith\r\nDeath Age: \t73\r\nBirth Date: \t11 Jul 1926\r\n"
            "Registration Date: \tMar 2000\r\nRegistration district: \tSheffield\r\n"
            "Inferred County: \tSouth Yorkshire\r\nRegister Number: \tC86A\r\n"
            "District and Subdistrict: \t0481C\r\nEntry Number: \t243")
VOLUME = ("Name: \tMary Ann F Brown\r\nDeath Age: \t74\r\nBirth Date: \t12 Jun 1917\r\n"
          "Registration Date: \tJul 1991\r\nRegistration District: \tGrimsby\r\nVolume: \t7\r\n"
          "Page: \t492\r\nSource Citation\r\n\r\nGeneral Register Office; United Kingdom")


class AncestryDeathsMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        defs = "<Root><Fields>" + "".join(
            f"<Field><FieldName>{n}</FieldName></Field>" for n in TEMPLATE_6_FIELDS) + "</Fields></Root>"
        conn = sqlite3.connect(self.db)
        conn.executescript("""
            CREATE TABLE SourceTemplateTable (TemplateID INTEGER PRIMARY KEY, Name TEXT, FieldDefs BLOB);
            CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, Name TEXT, TemplateID INTEGER,
                Fields BLOB, ActualText TEXT, Comments TEXT, UTCModDate FLOAT);
            CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER,
                CitationName TEXT, ActualText TEXT, Fields BLOB, UTCModDate FLOAT);
            CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, EventType INTEGER,
                OwnerType INTEGER, OwnerID INTEGER);
            CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER,
                OwnerType INTEGER, OwnerID INTEGER, UTCModDate FLOAT);
            CREATE TABLE MultimediaTable (MediaID INTEGER PRIMARY KEY, MediaPath TEXT, MediaFile TEXT);
            CREATE TABLE MediaLinkTable (LinkID INTEGER PRIMARY KEY, MediaID INTEGER,
                OwnerType INTEGER, OwnerID INTEGER, UTCModDate FLOAT);
            INSERT INTO EventTable VALUES (1, 1030, 0, 1), (2, 1, 0, 1), (3, 2, 0, 2);
            INSERT INTO CitationLinkTable (CitationID, OwnerType, OwnerID) VALUES (10, 2, 1), (11, 2, 2), (12, 2, 3);
            INSERT INTO MultimediaTable VALUES (1, 'H:\\My Drive\\Records\\Deaths\\Britain\\Transcripts', 'SMI-J.pdf');
            INSERT INTO MediaLinkTable (MediaID, OwnerType, OwnerID) VALUES (1, 4, 10), (1, 4, 11);
        """)
        conn.execute("INSERT INTO SourceTemplateTable VALUES (6, 'Complex Website', ?)", (defs.encode(),))
        conn.execute("INSERT INTO SourceTable VALUES (704, 'Death Register - UK - Ancestry', 10003, ?,"
                     " 'www.ancestry.co.uk', 'Source Information ...', 1.0)", (b"<Root><Fields></Fields></Root>",))
        conn.executemany("INSERT INTO CitationTable VALUES (?, 704, 'old', ?, NULL, 1.0)",
                         [(10, REGISTER), (11, REGISTER), (12, VOLUME)])
        conn.commit()
        conn.close()
        patcher = mock.patch.object(ancestry_deaths, "list_windows_file_dates",
                                    return_value={f"{FOLDER}\\smi-j.pdf".lower(): date(2019, 3, 1)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_script(self, *options: str) -> tuple[int, str]:
        return self.run_main(ancestry_deaths.main, str(self.db), "--config", str(EXAMPLE_CONFIG), *options)

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_script()
        self.assertEqual(code, 0)
        self.assertIn("3 citations; 2 to convert; 1 to merge; 0 cannot convert\nDry run: nothing changed.", out)
        self.assertEqual(self.db.read_bytes(), before)
        text = self.output_path("ancestry_deaths", "death_register").read_text(encoding="utf-8")
        self.assertIn("   C11 -> C10 John smith [P1]\n", text)
        self.assertIn("   C12: no scan attached; access date left blank\n", text)

    def test_apply_writes_source_and_citations(self):
        code, out = self.run_script("--apply")
        self.assertEqual(code, 0)
        self.assertIn("Applied: source S704, 2 citations updated, 1 merged.", out)
        conn = sqlite3.connect(self.db)
        template, fields, text, comments = conn.execute(
            "SELECT TemplateID, Fields, ActualText, Comments FROM SourceTable").fetchone()
        rows = dict((cid, (t, f)) for cid, t, f in conn.execute(
            "SELECT CitationID, ActualText, Fields FROM CitationTable"))
        conn.close()
        self.assertEqual((template, comments), (6, ""))
        self.assertEqual(read_fields(fields)["WebsiteTitle"], "Ancestry")
        self.assertTrue(text.startswith("England and Wales GRO death index entries"))
        self.assertNotIn(11, rows)
        self.assertEqual(rows[10][0], "Deaths 2000\r\nSmith\tJohn\t11 Jul 1926\tSheffield\t03.00\tC86A\t0481C\t243")
        self.assertEqual(read_fields(rows[10][1]), {
            "AccessDate": "1 March 2019",
            "SpecificItem": "entry for John Smith, born 11 July 1926, Sheffield, registered March 2000,"
                            " register C86A, district and subdistrict 0481C, entry 243",
            "Citing": "General Register Office, England and Wales Civil Registration Indexes",
        })
        self.assertEqual(rows[12][0], "Deaths 1991\r\nBrown\tMary Ann F\t12 Jun 1917\tGrimsby\t07.91\t7\t492")

    def test_no_arguments_prints_usage(self):
        code, out = self.run_main(ancestry_deaths.main)
        self.assertEqual(code, 2)
        self.assertIn("Usage: python ancestry_deaths.py", out)


if __name__ == "__main__":
    unittest.main()
