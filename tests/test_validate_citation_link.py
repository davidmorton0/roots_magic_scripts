import unittest

from validate_support import ValidateTestCase, summary_counts

import validate_citation_link

EXPECTED_COUNTS = {
    "citation_link_orphan": "2",
    "citation_link_quality": "1",
}
EXPECTED_LINES = [
    "Census: RG11 [C1] -> owner type 7 id 50 missing",
    "citation C9 missing (owner type 2 id 1)",
    "link 3: Census: RG12 [C2] -> Death 1910 - John Smith [P1] [E2] quality 'PD'",
]


class ValidateCitationLinkMainTest(ValidateTestCase):
    def test_summary_and_details(self):
        code, out = self.run_validate(validate_citation_link.main)
        self.assertEqual(code, 0)
        self.assertEqual(summary_counts(out), EXPECTED_COUNTS)
        details = self.output_path("validate_citation_link", "validate").read_text(encoding="utf-8")
        for line in EXPECTED_LINES:
            self.assertIn(line, details)


if __name__ == "__main__":
    unittest.main()
