import sqlite3
import unittest
from datetime import date
from unittest import mock

from support import ScriptTestCase

import ancestry_birth_index
from rmutils import fields_blob, read_fields

WILLIAM_FIELDS = {
    "AccessDate": "8 November 2020",
    "SpecificItem": "entry for William A Morton, Basford, vol. 7b, p. 252, mother's maiden name Blythe",
    "Citing": "General Register Office, Births registered in October, November, and December 1934",
}
OLD_ETHEL = {"Name": "Ethel Williams", "Series": "", "Book": "Basford Q1", "Entry": "1904"}

SETUP_SQL = """
CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, Name TEXT, TemplateID INTEGER,
    Fields BLOB, UTCModDate FLOAT);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER,
    CitationName TEXT, ActualText TEXT, Fields BLOB, UTCModDate FLOAT);
CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER,
    OwnerType INTEGER, OwnerID INTEGER);
CREATE TABLE MediaLinkTable (LinkID INTEGER PRIMARY KEY, MediaID INTEGER,
    OwnerType INTEGER, OwnerID INTEGER);
INSERT INTO CitationLinkTable VALUES (4471, 4471, 2, 5766), (4522, 4522, 2, 5818), (4523, 4523, 2, 5818);
INSERT INTO MediaLinkTable VALUES (4054, 2080, 4, 4471), (4220, 2203, 4, 4522), (4221, 2203, 4, 4523);
"""


class AncestryBirthIndexMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.executemany(
            "INSERT INTO SourceTable VALUES (?, ?, ?, ?, 1.0)",
            [(583, "Birth Register UK", 6, b"<Root></Root>"),
             (590, "Birth Register - UK - Ancestry", 10003, b"<Root></Root>")],
        )
        conn.executemany(
            "INSERT INTO CitationTable VALUES (?, ?, 'old', ?, ?, 1.0)",
            [(4471, 583, "Name: William A Morton", fields_blob(WILLIAM_FIELDS, declaration=False)),
             (4522, 590, "", fields_blob(OLD_ETHEL, declaration=False)),
             (4523, 590, "", fields_blob(OLD_ETHEL, declaration=False))],
        )
        conn.commit()
        conn.close()
        patcher = mock.patch.object(
            ancestry_birth_index, "windows_file_modified", return_value=date(2020, 11, 10)
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def query(self, sql: str) -> list[tuple]:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute(sql).fetchall()
        finally:
            conn.close()

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(ancestry_birth_index.main, str(self.db))
        self.assertEqual(code, 0)
        self.assertIn("C4523: delete, with citation links [4523] and media links [4221]", out)
        self.assertIn("Dry run: nothing changed.", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply(self):
        code, out = self.run_main(ancestry_birth_index.main, str(self.db), "--apply")
        self.assertEqual(code, 0)

        (template, blob), = self.query("SELECT TemplateID, Fields FROM SourceTable WHERE SourceID = 590")
        self.assertEqual(template, 6)
        self.assertEqual(read_fields(blob)["WebsiteTitle"], "Ancestry")

        rows = {cid: (sid, read_fields(blob), text) for cid, sid, blob, text in self.query(
            "SELECT CitationID, SourceID, Fields, ActualText FROM CitationTable")}
        self.assertEqual(sorted(rows), [4471, 4522])
        self.assertEqual(rows[4471][0], 590)
        self.assertTrue(rows[4471][1]["SpecificItem"].endswith(
            "(England & Wales, Civil Registration Birth Index, 1916-2007)"))
        self.assertEqual(rows[4522][1], {
            "AccessDate": "10 November 2020",
            "SpecificItem": "entry for Ethel Williams, Basford, vol. 7b, p. 273"
                            " (England & Wales, Civil Registration Birth Index, 1837-1915)",
            "Citing": "General Register Office, Births registered in January, February, and March 1904",
        })
        self.assertTrue(rows[4522][2].startswith("Births Mar 1904\nWilliams\tEthel\tBasford\t7b\t273"))
        self.assertEqual(self.query("SELECT LinkID FROM CitationLinkTable ORDER BY LinkID"), [(4471,), (4522,)])
        self.assertEqual(self.query("SELECT LinkID FROM MediaLinkTable ORDER BY LinkID"), [(4054,), (4220,)])

    def test_refuses_when_already_done(self):
        self.run_main(ancestry_birth_index.main, str(self.db), "--apply")
        code, out = self.run_main(ancestry_birth_index.main, str(self.db), "--apply")
        self.assertEqual(code, 1)
        self.assertIn("Not possible", out)


if __name__ == "__main__":
    unittest.main()
