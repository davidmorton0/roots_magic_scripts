import unittest

from validate_support import ValidateTestCase, summary_counts

import validate_event

EXPECTED_COUNTS = {
    "record_event_no_citation": "2",
    "event_no_citation": "4",
    "event_no_date": "1",
    "event_no_place": "0",
    "fact_year_mismatch": "0",
    "date_style_unusual": "0",
    "event_before_birth": "0",
    "event_after_death": "0",
    "event_owner_missing": "1",
    "event_date_form": "1",
    "event_sort_date": "1",
    "witness_orphan": "2",
}
EXPECTED_LINES = [
    "Birth [E6] -> person 96 missing",
    "'T1881 census' text date, not an encoded date",
    "[E8]: SortDate 5, expected",
    "witness 1 on Marriage 1865 - John Smith & Mary Smith [F1] [E5]: person P95 missing",
    "witness 2: event E999 missing",
]


class ValidateEventMainTest(ValidateTestCase):
    def test_summary_and_details(self):
        code, out = self.run_validate(validate_event.main)
        self.assertEqual(code, 0)
        self.assertEqual(summary_counts(out), EXPECTED_COUNTS)
        details = self.output_path("validate_event", "validate").read_text(encoding="utf-8")
        for line in EXPECTED_LINES:
            self.assertIn(line, details)


if __name__ == "__main__":
    unittest.main()
