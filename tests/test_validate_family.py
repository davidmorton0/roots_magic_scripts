import unittest

from validate_support import ValidateTestCase, summary_counts

import validate_family

EXPECTED_COUNTS = {
    "family_one_partner": "1",
    "parent_age": "1",
    "family_event_age": "1",
    "family_partner_missing": "1",
    "child_orphan": "4",
}
EXPECTED_LINES = [
    "F2: mother P98 missing",
    "Tom Smith [P3] child of F50: family missing",
    "child P97 of John Smith & Mary Smith [F1]: person missing",
    "(missing person) [P97] listed 2 times as a child of John Smith & Mary Smith [F1]",
]


class ValidateFamilyMainTest(ValidateTestCase):
    def test_summary_and_details(self):
        code, out = self.run_validate(validate_family.main)
        self.assertEqual(code, 0)
        self.assertEqual(summary_counts(out), EXPECTED_COUNTS)
        details = self.output_path("validate_family", "validate").read_text(encoding="utf-8")
        for line in EXPECTED_LINES:
            self.assertIn(line, details)


if __name__ == "__main__":
    unittest.main()
