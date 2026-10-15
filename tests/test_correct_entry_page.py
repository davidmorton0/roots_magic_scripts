import sqlite3
import unittest

from support import ScriptTestCase

import correct_entry_page
from rmutils import fields_blob, read_fields

FIELDS = {"AccessDate": "1 May 2019", "SpecificItem": "entry for Albert Doe, Ecclesall B., vol. 9c, p. 7?40",
          "Citing": "General Register Office, Births registered in April, May, and June 1923"}
SETUP_SQL = """
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, CitationName TEXT, ActualText TEXT,
    Comments TEXT, Fields BLOB, UTCModDate FLOAT);
CREATE TABLE MediaLinkTable (LinkID INTEGER PRIMARY KEY, MediaID INTEGER, OwnerType INTEGER, OwnerID INTEGER);
CREATE TABLE MultimediaTable (MediaID INTEGER PRIMARY KEY, RefNumber TEXT, Description TEXT, UTCModDate FLOAT);
INSERT INTO MediaLinkTable (MediaID, OwnerType, OwnerID) VALUES (1, 4, 10);
INSERT INTO MultimediaTable VALUES (1, '1923 Q2 Ecclesall B. 9c 7?40', 'Albert Doe, Ecclesall B., vol. 9c, p. 7?40. Image.', 1.0);
"""


class CorrectEntryPageMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.execute("INSERT INTO CitationTable VALUES (10, 'old', 'Doe Albert 7?40', '', ?, 1.0)",
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
        code, out = self.run_main(correct_entry_page.main, str(self.db), "--citation", "10",
                                  "--old", "7?40", "--new", "740", "--note", "n")
        self.assertEqual(code, 0)
        self.assertIn("M1: reference '1923 Q2 Ecclesall B. 9c 7?40' -> '1923 Q2 Ecclesall B. 9c 740'", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply(self):
        code, _ = self.run_main(correct_entry_page.main, str(self.db), "--citation", "10",
                                "--old", "7?40", "--new", "740", "--note", "Page confirmed", "--apply")
        self.assertEqual(code, 0)
        name, blob, text, note = self.query(
            "SELECT CitationName, Fields, ActualText, Comments FROM CitationTable")[0]
        self.assertEqual(read_fields(blob)["SpecificItem"], "entry for Albert Doe, Ecclesall B., vol. 9c, p. 740")
        self.assertIn("p. 740;", name)
        self.assertEqual((text, note), ("Doe Albert 7?40", "Page confirmed"))
        self.assertEqual(self.query("SELECT RefNumber, Description FROM MultimediaTable"),
                         [("1923 Q2 Ecclesall B. 9c 740", "Albert Doe, Ecclesall B., vol. 9c, p. 740. Image.")])

    def test_refuses_when_page_not_found(self):
        code, out = self.run_main(correct_entry_page.main, str(self.db), "--citation", "10",
                                  "--old", "999", "--new", "740", "--note", "n")
        self.assertEqual(code, 1)
        self.assertIn("has no 'p. 999'", out)


if __name__ == "__main__":
    unittest.main()
