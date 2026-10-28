import unittest

from validate_support import ValidateTestCase, summary_counts

import validate_name

EXPECTED_COUNTS = {
    "name_owner_missing": "1",
    "name_part_blank": "1",
    "name_spaces": "1",
    "name_case": "1",
    "name_duplicate": "1",
    "name_date_form": "1",
}
EXPECTED_LINES = [
    "Ghost Name [N7] -> P99 missing",
    "Smith (alternative) [N6] of Tom Smith [P3]: no given names",
    "of John Smith [P1]: Given ' John'",
    "[N4] of ann BROWN [P4]: Given 'ann', Surname 'BROWN'",
    "John Smith of John Smith [P1] [N1, N5]",
    "month or day out of range in 18501301",
]


class ValidateNameMainTest(ValidateTestCase):
    def test_summary_and_details(self):
        code, out = self.run_validate(validate_name.main)
        self.assertEqual(code, 0)
        self.assertEqual(summary_counts(out), EXPECTED_COUNTS)
        details = self.output_path("validate_name", "validate").read_text(encoding="utf-8")
        for line in EXPECTED_LINES:
            self.assertIn(line, details)


if __name__ == "__main__":
    unittest.main()
