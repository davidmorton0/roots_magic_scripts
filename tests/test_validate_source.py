import unittest

from validate_support import ValidateTestCase, summary_counts

import validate_source

EXPECTED_COUNTS = {
    "source_unused": "1",
}
EXPECTED_LINES = [
    "Unused [S2]",
]


class ValidateSourceMainTest(ValidateTestCase):
    def test_summary_and_details(self):
        code, out = self.run_validate(validate_source.main)
        self.assertEqual(code, 0)
        self.assertEqual(summary_counts(out), EXPECTED_COUNTS)
        details = self.output_path("validate_source", "validate").read_text(encoding="utf-8")
        for line in EXPECTED_LINES:
            self.assertIn(line, details)


if __name__ == "__main__":
    unittest.main()
