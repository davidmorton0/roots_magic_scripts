import sqlite3
import unittest

from support import ScriptTestCase

import remove_register_events

SETUP_SQL = """
CREATE TABLE EventTable (EventID INTEGER PRIMARY KEY, EventType INTEGER, OwnerType INTEGER,
    OwnerID INTEGER, IsPrimary INTEGER, PlaceID INTEGER, Date TEXT, UTCModDate FLOAT);
CREATE TABLE PlaceTable (PlaceID INTEGER PRIMARY KEY, Name TEXT);
CREATE TABLE CitationLinkTable (LinkID INTEGER PRIMARY KEY, CitationID INTEGER,
    OwnerType INTEGER, OwnerID INTEGER);
CREATE TABLE MediaLinkTable (LinkID INTEGER PRIMARY KEY, MediaID INTEGER,
    OwnerType INTEGER, OwnerID INTEGER);
CREATE TABLE TaskLinkTable (LinkID INTEGER PRIMARY KEY, TaskID INTEGER,
    OwnerType INTEGER, OwnerID INTEGER);
CREATE TABLE URLTable (LinkID INTEGER PRIMARY KEY, OwnerType INTEGER, OwnerID INTEGER);
CREATE TABLE WitnessTable (WitnessID INTEGER PRIMARY KEY, EventID INTEGER);
CREATE TABLE AddressLinkTable (LinkID INTEGER PRIMARY KEY, OwnerType INTEGER, OwnerID INTEGER);

INSERT INTO PlaceTable VALUES (5, 'Medway, Kent'), (6, 'Gillingham, Kent');
INSERT INTO EventTable VALUES
    -- person 1: register event 1 (Medway); Birth event 2 has no place
    (1, 1024, 0, 1, 0, 5, 'D-+18860100..+18860300..', 1.0),
    (2, 1, 0, 1, 1, 0, 'D.+18860214..+00000000..', 1.0),
    -- person 2: register event 3; Birth event 4 already has a place
    (3, 1024, 0, 2, 0, 5, 'D-+18840400..+18840600..', 1.0),
    (4, 1, 0, 2, 1, 6, 'D.+18840500..+00000000..', 1.0),
    -- person 3: register event 5, no Birth event
    (5, 1024, 0, 3, 0, 5, 'D-+18900100..+18900300..', 1.0),
    -- person 4: register event 6 still has media; Birth event 7
    (6, 1024, 0, 4, 0, 5, 'D-+18920100..+18920300..', 1.0),
    (7, 1, 0, 4, 1, 0, 'D.+18920100..+00000000..', 1.0),
    -- person 1: a second register event 8, kept by --keep
    (8, 1024, 0, 1, 0, 5, 'D-+19170100..+19170300..', 1.0);
INSERT INTO MediaLinkTable (MediaID, OwnerType, OwnerID) VALUES (1, 2, 6);
"""


class RemoveRegisterEventsMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript(SETUP_SQL)
        conn.commit()
        conn.close()

    def events(self) -> list[tuple]:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute(
                "SELECT EventID, EventType, PlaceID FROM EventTable ORDER BY EventID"
            ).fetchall()
        finally:
            conn.close()

    def test_dry_run_reports_and_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(remove_register_events.main, str(self.db), "--keep", "8")

        self.assertEqual(code, 0)
        self.assertIn("5 register events; 2 to delete; 3 not deleted\nDry run: nothing changed.", out)
        self.assertEqual(self.db.read_bytes(), before)
        text = self.output_path("remove_register_events", "birth_register").read_text(encoding="utf-8")
        for line in [
            "   E5 Albert Brown, Jr [P3] D-+18900100..+18900300..: person has no Birth event",
            "   E6 (no primary name) [P4] D-+18920100..+18920300..: still has media",
            "   E8 John smith [P1] D-+19170100..+19170300..: kept as requested",
            "   E2 John smith [P1]: Medway, Kent [L5]",
            "   E3 Dr Mary Brown [P2] D-+18840400..+18840600.., Medway, Kent",
        ]:
            self.assertIn(line + "\n", text)

    def test_apply_copies_place_and_deletes(self):
        code, out = self.run_main(
            remove_register_events.main, str(self.db), "--keep", "8", "--apply"
        )

        self.assertEqual(code, 0)
        self.assertIn("Applied: 2 register events deleted; 1 places copied.", out)
        self.assertEqual(
            self.events(),
            [(2, 1, 5), (4, 1, 6), (5, 1024, 5), (6, 1024, 5), (7, 1, 0), (8, 1024, 5)],
        )

    def test_no_arguments_prints_usage(self):
        code, out = self.run_main(remove_register_events.main)
        self.assertEqual(code, 2)
        self.assertIn("Usage: python remove_register_events.py", out)


if __name__ == "__main__":
    unittest.main()
