import unittest
from datetime import date
from unittest import mock

from support import ScriptTestCase

import file_input_scan

INPUT = "H:\\Rec\\Input"
FOLDER = "H:\\Rec\\Census\\1881"


class FileInputScanMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.config = self.tmp / "config.toml"
        self.config.write_text(f"scan_root = 'H:\\Rec'\ninput_folder = '{INPUT}'\n", encoding="utf-8")
        self.files = {f"{INPUT}\\new.jpg": date(2026, 1, 1), FOLDER: date(2025, 1, 1),
                      f"{FOLDER}\\DOE-J-NIB-1881.jpg": date(2020, 1, 1),
                      f"{FOLDER}\\DOE-J-NIB-1881-P2.jpg": date(2020, 1, 1),
                      f"{FOLDER}\\DOE-JA-NIB-1881.jpg": date(2020, 1, 1)}
        for name, fake in (("windows_file_modified", lambda p: self.files.get(p)),
                           ("list_windows_files", lambda root: [p for p in self.files if p.startswith(root + "\\")]),
                           ("move_windows_file", self.move)):
            patcher = mock.patch.object(file_input_scan, name, side_effect=fake)
            self.addCleanup(patcher.stop)
            setattr(self, name, patcher.start())

    def move(self, path: str, new_path: str) -> None:
        self.files[new_path] = self.files.pop(path)

    def run_script(self, *args: str) -> tuple[int, str]:
        return self.run_main(file_input_scan.main, *args, "--config", str(self.config))

    def test_dry_run_reports_date_and_same_names(self):
        code, out = self.run_script("new.jpg", "Census\\1881\\DOE-J-NIB-1881-R2.jpg")
        self.assertEqual(code, 0, out)
        self.assertIn(f"Move {INPUT}\\new.jpg\n  -> {FOLDER}\\DOE-J-NIB-1881-R2.jpg", out)
        self.assertIn("Last modified (access date, G16): 2026-01-01 (1 January 2026)", out)
        self.assertIn("   DOE-J-NIB-1881-P2.jpg\n   DOE-J-NIB-1881.jpg\n", out)
        self.assertNotIn("DOE-JA", out)
        self.move_windows_file.assert_not_called()

    def test_apply_moves(self):
        code, out = self.run_script("new.jpg", f"{FOLDER}\\SMI-T-NIB-1881.jpg", "--apply")
        self.assertEqual(code, 0, out)
        self.assertIn("No file with the same base name in the target folder.", out)
        self.move_windows_file.assert_called_once_with(f"{INPUT}\\new.jpg", f"{FOLDER}\\SMI-T-NIB-1881.jpg")

    def test_refusals(self):
        code, out = self.run_script("missing.jpg", "Census\\1881\\X.jpg", "--apply")
        self.assertEqual(code, 1)
        self.assertIn(f"Not found: {INPUT}\\missing.jpg", out)
        code, out = self.run_script("new.jpg", "Census\\1881\\DOE-J-NIB-1881.jpg", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("already exists", out)
        self.move_windows_file.assert_not_called()


if __name__ == "__main__":
    unittest.main()
