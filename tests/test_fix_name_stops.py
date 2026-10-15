import sqlite3
import unittest

from support import ScriptTestCase

import fix_name_stops
from rmutils import fields_blob, read_fields

CITING = "General Register Office, Births registered in July, August, and September 1890"


def fields(item: str) -> bytes:
    return fields_blob({"AccessDate": "1 May 2019", "SpecificItem": item, "Citing": CITING},
                       declaration=False)


SETUP_SQL = """
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER, CitationName TEXT,
    Fields BLOB, ActualText TEXT, UTCModDate FLOAT);
CREATE TABLE MediaLinkTable (LinkID INTEGER PRIMARY KEY, MediaID INTEGER, OwnerType INTEGER,
    OwnerID INTEGER);
CREATE TABLE MultimediaTable (MediaID INTEGER PRIMARY KEY, Description TEXT, UTCModDate FLOAT);
INSERT INTO MediaLinkTable (MediaID, OwnerType, OwnerID) VALUES (1, 4, 10);
INSERT INTO MultimediaTable VALUES
    (1, 'Births registered in July, August, and September 1890: Ada Ellen. Wells, Leeds, vol. 9b, p. 1. Image.', 1.0);
"""


class FixNameStopsMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.executemany(
            "INSERT INTO CitationTable VALUES (?, 583, 'old', ?, 'Wells Ada Ellen.', 1.0)",
            [(10, fields("entry for Ada Ellen. Wells, Leeds, vol. 9b, p. 1")),
             (11, fields("entry for John S. Smith, Leeds, vol. 9b, p. 2"))],
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
        code, out = self.run_main(fix_name_stops.main, str(self.db))
        self.assertEqual(code, 0)
        self.assertIn("C10: 'Ada Ellen. Wells' -> 'Ada Ellen Wells'\n", out)
        self.assertIn("1 citations; 1 scan descriptions\nDry run: nothing changed.", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply(self):
        code, out = self.run_main(fix_name_stops.main, str(self.db), "--apply")
        self.assertEqual(code, 0)
        rows = {cid: (name, read_fields(blob), text) for cid, name, blob, text in self.query(
            "SELECT CitationID, CitationName, Fields, ActualText FROM CitationTable")}
        self.assertEqual(rows[10][1]["SpecificItem"], "entry for Ada Ellen Wells, Leeds, vol. 9b, p. 1")
        self.assertEqual(rows[10][0], f"1 May 2019; entry for Ada Ellen Wells, Leeds, vol. 9b, p. 1; {CITING}")
        self.assertEqual(rows[10][2], "Wells Ada Ellen.")  # transcription unchanged
        self.assertEqual(rows[11][1]["SpecificItem"], "entry for John S. Smith, Leeds, vol. 9b, p. 2")
        self.assertEqual(rows[11][0], "old")
        self.assertIn(": Ada Ellen Wells, Leeds,", self.query("SELECT Description FROM MultimediaTable")[0][0])


if __name__ == "__main__":
    unittest.main()
