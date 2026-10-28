import unittest

from validate_support import ValidateTestCase, summary_counts

import validate_media

EXPECTED_COUNTS = {
    "scan_not_in_db": "1",
    "media_file_missing": "1",
    "media_outside_root": "0",
    "media_unlinked": "1",
    "media_not_on_citation": "0",
    "media_type_mismatch": "1",
    "media_duplicate": "0",
    "media_link_orphan": "0",
    "media_date_form": "1",
    "media_sort_date": "1",
}
EXPECTED_LINES = [
    "H:\\My Drive\\Records\\Census\\new.jpg",
    "[M1] 'T19/02/2019 22:42:21': text date, not an encoded date",
    "[M2] D.+18810403..+00000000..: SortDate 0, expected",
]


class ValidateMediaMainTest(ValidateTestCase):
    def test_summary_and_details(self):
        code, out = self.run_validate(validate_media.main, "--scan-list", str(self.scan_list))
        self.assertEqual(code, 0)
        self.assertEqual(summary_counts(out), EXPECTED_COUNTS)
        details = self.output_path("validate_media", "validate").read_text(encoding="utf-8")
        for line in EXPECTED_LINES:
            self.assertIn(line, details)

    def test_no_scans_skips_disk_checks(self):
        code, out = self.run_validate(validate_media.main, "--no-scans")
        self.assertEqual(code, 0)
        counts = summary_counts(out)
        self.assertEqual((counts["scan_not_in_db"], counts["media_file_missing"]), ("skipped", "skipped"))
        self.assertEqual(counts["media_type_mismatch"], "1")


if __name__ == "__main__":
    unittest.main()
