import sqlite3
import unittest

from support import ScriptTestCase

import familysearch_ireland_births
from rmutils import fields_blob, read_fields

SETUP_SQL = """
CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, Name TEXT, TemplateID INTEGER,
    Fields BLOB, UTCModDate FLOAT);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER, CitationName TEXT,
    ActualText TEXT, Fields BLOB, UTCModDate FLOAT);
INSERT INTO SourceTable VALUES (584, 'Birth Register - Ireland - FamilySearch', 10001, X'3c526f6f742f3e', 1.0);
"""


def old_fields(name: str) -> bytes:
    return fields_blob({"Name": name, "Form": "", "CertificateNo": "", "Date": ""}, declaration=False)


class FamilySearchIrelandBirthsMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.executemany(
            "INSERT INTO CitationTable VALUES (?, 584, 'old', 'text', ?, 1.0)",
            [(2663, old_fields("Joseph Gracey")), (3334, old_fields("James Gracey"))],
        )
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
        code, out = self.run_main(familysearch_ireland_births.main, str(self.db))
        self.assertEqual(code, 0)
        self.assertIn("Dry run: nothing changed.", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply(self):
        code, _ = self.run_main(familysearch_ireland_births.main, str(self.db), "--apply")
        self.assertEqual(code, 0)
        (template, blob), = self.query("SELECT TemplateID, Fields FROM SourceTable")
        self.assertEqual((template, read_fields(blob)["WebsiteTitle"]), (6, "FamilySearch"))
        rows = {cid: (name, read_fields(blob), text) for cid, name, blob, text in self.query(
            "SELECT CitationID, CitationName, Fields, ActualText FROM CitationTable")}
        self.assertEqual(rows[2663][1]["SpecificItem"], "entry for Joseph Gracey, Lurgan, vol. 1, p. 667")
        self.assertEqual(rows[3334][1]["AccessDate"], "10 March 2018")
        self.assertTrue(rows[3334][0].startswith("10 March 2018; entry for James Gracey"))
        self.assertEqual(rows[2663][2], "text")

    def test_refuses_second_run(self):
        self.run_main(familysearch_ireland_births.main, str(self.db), "--apply")
        code, out = self.run_main(familysearch_ireland_births.main, str(self.db), "--apply")
        self.assertEqual(code, 1)
        self.assertIn("already on template 6", out)


if __name__ == "__main__":
    unittest.main()
