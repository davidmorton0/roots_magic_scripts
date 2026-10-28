import unittest

from validate_support import ValidateTestCase, summary_counts

import validate_task

EXPECTED_COUNTS = {
    "task_unlinked": "1",
    "task_link_orphan": "3",
    "task_date_form": "1",
}
EXPECTED_LINES = [
    "Orphan task [T2]",
    "link 2: task T7 missing",
    "link 3: Find birth [T1] -> person P94 missing",
    "link 4: Find birth [T1] -> owner type 3 id 1 not checked",
    "Orphan task [T2] Date1 'D.+2020': form not known",
]


class ValidateTaskMainTest(ValidateTestCase):
    def test_summary_and_details(self):
        code, out = self.run_validate(validate_task.main)
        self.assertEqual(code, 0)
        self.assertEqual(summary_counts(out), EXPECTED_COUNTS)
        details = self.output_path("validate_task", "validate").read_text(encoding="utf-8")
        for line in EXPECTED_LINES:
            self.assertIn(line, details)


if __name__ == "__main__":
    unittest.main()
