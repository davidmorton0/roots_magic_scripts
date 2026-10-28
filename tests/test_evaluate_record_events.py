import unittest

from evaluate_support import EvaluateTestCase

import evaluate_record_events

TABLE = """# Test

## Record facts

| Record fact | Main fact | Match |
|---|---|---|
| `Directory` | Residence | date |
| `Marriage Register - UK` | Marriage | primary |
| `Newspaper Article` | - | - |
"""


class EvaluateRecordEventsMainTest(EvaluateTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.table.write_text(TABLE, encoding="utf-8")
        self.citations()

    def run_events(self, *args: str) -> tuple[int, str]:
        return self.run_main(evaluate_record_events.main, str(self.db), "--table", str(self.table), *args)

    def details(self) -> str:
        return self.output_path("evaluate_record_events", "people").read_text(encoding="utf-8")

    def test_all(self):
        code, out = self.run_events("--all")
        self.assertEqual(code, 0)
        self.assertIn("Directory: 2 events; CONVERT 1, COPY 1", out)
        details = self.details()
        for line in (
                "E14 Directory D.+18810403..+00000000.. - P1 John Doe: COPY (main fact E13 Residence",
                "   - place detail L3",
                "   - citation C20",
                "   - description 'grocer'",
                "E15 Directory D.+19000000..+00000000.. - P3 Tom Doe: CONVERT",
                "no Residence dated D.+19000000..+00000000..: change this event's type to 29 (Residence)",
                "E16 Newspaper Article . - P1 John Doe: DECIDE",
                "E18 Marriage Register - UK D.+18750000..+00000000.. - P2 Mary Doe: READY (main fact E17 Marriage",
        ):
            self.assertIn(line, details)

    def test_selection(self):
        code, out = self.run_events("--source", "2")
        self.assertIn("Newspaper Article: 1 events; DECIDE 1", out)
        code, out = self.run_events("--event", "10")
        self.assertEqual(code, 1)
        self.assertIn("Not record events or not found: E10", out)
        code, out = self.run_events("--fact", "1035")
        self.assertIn("Directory: 2 events", out)

    def test_skill_table(self):
        rows = evaluate_record_events.load_rows(evaluate_record_events.TABLE_FILE, "Record facts", "Record fact")
        self.assertGreater(len(rows), 5)


if __name__ == "__main__":
    unittest.main()
