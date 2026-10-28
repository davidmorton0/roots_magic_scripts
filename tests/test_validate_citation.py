import unittest

from validate_support import ValidateTestCase, summary_counts

import validate_citation

EXPECTED_COUNTS = {
    "citation_no_media": "1",
    "citation_unused": "0",
}
EXPECTED_LINES = [
    "Census: RG12 [C2] - Death 1910 - John Smith [P1] [E2]",
]


class ValidateCitationMainTest(ValidateTestCase):
    def test_summary_and_details(self):
        code, out = self.run_validate(validate_citation.main)
        self.assertEqual(code, 0)
        self.assertEqual(summary_counts(out), EXPECTED_COUNTS)
        details = self.output_path("validate_citation", "validate").read_text(encoding="utf-8")
        for line in EXPECTED_LINES:
            self.assertIn(line, details)


if __name__ == "__main__":
    unittest.main()
