import unittest

from validate_support import ValidateTestCase, summary_counts

import validate_place

EXPECTED_COUNTS = {
    "place_unused": "1",
    "place_detail_similar": "1",
}
EXPECTED_LINES = [
    "St Johns [L3] (detail)",
]


class ValidatePlaceMainTest(ValidateTestCase):
    def test_summary_and_details(self):
        code, out = self.run_validate(validate_place.main)
        self.assertEqual(code, 0)
        self.assertEqual(summary_counts(out), EXPECTED_COUNTS)
        details = self.output_path("validate_place", "validate").read_text(encoding="utf-8")
        for line in EXPECTED_LINES:
            self.assertIn(line, details)


if __name__ == "__main__":
    unittest.main()
