import unittest

from validate_support import ValidateTestCase, summary_counts

import validate_person

EXPECTED_COUNTS = {
    "person_no_name": "1",
    "person_sex_code": "1",
    "person_no_events": "2",
    "person_no_birth": "2",
    "person_unconnected": "2",
    "person_multiple_primary": "0",
    "birth_after_death": "0",
    "person_parent_family_bad": "1",
    "person_spouse_family_bad": "1",
}
EXPECTED_LINES = [
    "ann BROWN [P4] ParentID F9: family missing",
    "ann BROWN [P4] SpouseID John Smith & Mary Smith [F1]: not a partner in it",
]


class ValidatePersonMainTest(ValidateTestCase):
    def test_summary_and_details(self):
        code, out = self.run_validate(validate_person.main)
        self.assertEqual(code, 0)
        self.assertEqual(summary_counts(out), EXPECTED_COUNTS)
        details = self.output_path("validate_person", "validate").read_text(encoding="utf-8")
        for line in EXPECTED_LINES:
            self.assertIn(line, details)


if __name__ == "__main__":
    unittest.main()
