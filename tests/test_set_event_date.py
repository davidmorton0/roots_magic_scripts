import sqlite3
import unittest

from support import ScriptTestCase

import rmutils
import set_event_date

SETUP_SQL = """
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, EventType INTEGER, OwnerType INTEGER, OwnerID INTEGER,
    Date TEXT, SortDate INTEGER, UTCModDate FLOAT);
INSERT INTO EventTable VALUES (20, 1, 0, 2, 'D.+19020000..+00000000..', 1, 1.0);
"""
BETWEEN = "DR+19000900..+19010800.."


class SetEventDateMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.commit()
        conn.close()

    def event(self) -> tuple:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT Date, SortDate FROM EventTable WHERE EventID = 20").fetchone()
        finally:
            conn.close()

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(set_event_date.main, str(self.db), "--event", "20", "--date", BETWEEN)
        self.assertEqual(code, 0)
        self.assertIn(f"E20 (fact 1, owner type 0 ID 2): D.+19020000..+00000000.. -> {BETWEEN}", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply_sets_date_and_sort_date(self):
        code, _ = self.run_main(set_event_date.main, str(self.db), "--event", "20", "--date", BETWEEN, "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.event(), (BETWEEN, rmutils.sort_date(BETWEEN)))

    def test_apply_sets_after_date(self):
        # SortDate as RootsMagic 12 wrote it for "Aft 30 Dec 1912"
        code, _ = self.run_main(
            set_event_date.main, str(self.db), "--event", "20", "--date", "DA+19121230..+00000000..", "--apply"
        )
        self.assertEqual(code, 0)
        self.assertEqual(self.event(), ("DA+19121230..+00000000..", 6706298567474019359))

    def test_refused(self):
        code, out = self.run_main(set_event_date.main, str(self.db), "--event", "99", "--date", BETWEEN)
        self.assertEqual(code, 1)
        self.assertIn("E99 not found", out)
        code, out = self.run_main(set_event_date.main, str(self.db), "--event", "20", "--date", ".")
        self.assertEqual(code, 1)
        self.assertIn("no SortDate", out)


if __name__ == "__main__":
    unittest.main()
