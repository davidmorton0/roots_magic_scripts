import sqlite3
import unittest

from support import ScriptTestCase

import set_event_note

SETUP_SQL = """
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, EventType INTEGER, OwnerType INTEGER, OwnerID INTEGER,
    Note TEXT, UTCModDate FLOAT);
INSERT INTO EventTable VALUES (20, 2, 0, 2, 'Old note', 1.0);
"""
NOTE = "Stone gives d 1900; certificate gives 1901."


class SetEventNoteMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.commit()
        conn.close()

    def note(self) -> tuple:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT Note, UTCModDate FROM EventTable WHERE EventID = 20").fetchone()
        finally:
            conn.close()

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(set_event_note.main, str(self.db), "--event", "20", "--note", NOTE)
        self.assertEqual(code, 0)
        self.assertIn("E20 (fact 2, owner type 0 ID 2):", out)
        self.assertIn("old: 'Old note'", out)
        self.assertEqual(self.db.read_bytes(), before)

    def test_apply_sets_note(self):
        code, _ = self.run_main(set_event_note.main, str(self.db), "--event", "20", "--note", NOTE, "--apply")
        self.assertEqual(code, 0)
        note, mod = self.note()
        self.assertEqual(note, NOTE)
        self.assertNotEqual(mod, 1.0)

    def test_refused(self):
        code, out = self.run_main(set_event_note.main, str(self.db), "--event", "99", "--note", NOTE)
        self.assertEqual(code, 1)
        self.assertIn("E99 not found", out)


if __name__ == "__main__":
    unittest.main()
