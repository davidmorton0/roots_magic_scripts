import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from support import ScriptTestCase

import file

EXAMPLE_CONFIG = Path(__file__).resolve().parent.parent / "config.example.toml"
FOLDER = "H:\\My Drive\\Records\\Marriage - Church\\Britain"
SCAN = f"{FOLDER}\\Images\\SMI.J-BRO.M-MCIB-1880.jpg"
OTHER = f"{FOLDER}\\Images\\NEW.A-MCIB-1890.jpg"
LISTED = [
    (SCAN, date(2019, 1, 26)),
    (OTHER, date(2020, 9, 9)),
    (f"{FOLDER}\\Images\\unsure\\X.jpg", date(2020, 1, 1)),
    (f"{FOLDER}\\Unsorted\\Y.jpg", date(2020, 1, 1)),
]


class FileMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.disk = {SCAN.lower(): ("aaa", date(2019, 1, 26)), OTHER.lower(): ("bbb", date(2020, 9, 9))}
        fakes = {
            "list_windows_files_with_dates": lambda root: LISTED,
            "windows_file_modified": lambda p: self.disk[p.lower()][1] if p.lower() in self.disk else None,
            "windows_file_hash": lambda p: self.disk[p.lower()][0] if p.lower() in self.disk else None,
            "rename_windows_file": self.rename,
            "move_windows_file": self.move,
            "copy_windows_file": self.copy,
        }
        for name, fake in fakes.items():
            patcher = mock.patch.object(file, name, side_effect=fake)
            self.addCleanup(patcher.stop)
            setattr(self, name, patcher.start())

    def rename(self, path: str, new_name: str) -> None:
        self.disk[f"{path.rpartition(chr(92))[0]}\\{new_name}".lower()] = self.disk.pop(path.lower())

    def move(self, path: str, new_path: str) -> None:
        self.disk[new_path.lower()] = self.disk.pop(path.lower())

    def copy(self, path: str, new_path: str) -> None:
        self.disk[new_path.lower()] = self.disk[path.lower()]

    def run_file(self, *args: str) -> tuple[int, str]:
        return self.run_main(file.main, "--config", str(EXAMPLE_CONFIG), *args)

    def test_list_all_and_skipped(self):
        code, out = self.run_file("list", "Marriage - Church\\Britain")
        self.assertEqual(code, 0)
        self.list_windows_files_with_dates.assert_called_with(FOLDER)
        self.assertIn("   Images\\SMI.J-BRO.M-MCIB-1880.jpg  26 January 2019\n", out)
        self.assertIn("Unsorted\\Y.jpg", out)
        self.assertIn("4 files", out)
        code, out = self.run_file("list", FOLDER, "--skip")
        self.assertNotIn("X.jpg", out)
        self.assertNotIn("Y.jpg", out)
        self.assertIn("2 files", out)

    def test_info(self):
        code, out = self.run_file("info", SCAN)
        self.assertEqual(code, 0)
        self.assertIn("modified: 2019-01-26 (26 January 2019)", out)
        self.assertIn("SHA-256: aaa", out)
        self.assertEqual(self.run_file("info", f"{FOLDER}\\missing.jpg")[0], 1)

    def test_rename(self):
        code, out = self.run_file("rename", SCAN, "SMI.J-BRO.M-MCIB-1881.jpg")
        self.assertEqual(code, 0)
        self.assertIn("Dry run", out)
        self.rename_windows_file.assert_not_called()
        code, _ = self.run_file("rename", SCAN, "SMI.J-BRO.M-MCIB-1881.jpg", "--apply")
        self.assertEqual(code, 0)
        self.rename_windows_file.assert_called_once_with(SCAN, "SMI.J-BRO.M-MCIB-1881.jpg")

    def test_rename_refusals(self):
        code, out = self.run_file("rename", SCAN, "NEW.A-MCIB-1890.jpg", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("already exists", out)
        code, out = self.run_file("rename", SCAN, "Other\\x.jpg", "--apply")
        self.assertIn("is not a plain file name", out)
        code, out = self.run_file("rename", f"{FOLDER}\\missing.jpg", "x.jpg", "--apply")
        self.assertIn("file not found", out)
        self.rename_windows_file.assert_not_called()

    def test_move(self):
        target = f"{FOLDER}\\Transcripts\\SMI.J-BRO.M-MCIB-1880.jpg"
        self.assertEqual(self.run_file("move", SCAN, target)[0], 0)
        self.move_windows_file.assert_not_called()
        code, _ = self.run_file("move", SCAN, "Marriage - Church\\Britain\\Transcripts\\SMI.J-BRO.M-MCIB-1880.jpg",
                                "--apply")
        self.assertEqual(code, 0)
        self.move_windows_file.assert_called_once_with(SCAN, target)
        code, out = self.run_file("move", target, OTHER, "--apply")
        self.assertEqual(code, 1)
        self.assertIn("already exists", out)

    def test_copy(self):
        target = f"{FOLDER}\\copy.jpg"
        code, out = self.run_file("copy", SCAN, target, "--apply")
        self.assertEqual(code, 0)
        self.assertIn("Applied: file copied (SHA-256 aaa).", out)
        code, out = self.run_file("copy", SCAN, OTHER, "--apply")
        self.assertEqual(code, 1)
        self.assertIn("give --overwrite", out)
        self.assertEqual(self.run_file("copy", SCAN, OTHER, "--overwrite", "--apply")[0], 0)
        self.assertEqual(self.disk[OTHER.lower()][0], "aaa")

    def test_copy_reports_hash_mismatch(self):
        self.copy_windows_file.side_effect = lambda p, t: self.disk.__setitem__(t.lower(), ("zzz", date(2020, 1, 1)))
        code, out = self.run_file("copy", SCAN, f"{FOLDER}\\copy.jpg", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("hashes differ: aaa / zzz", out)


if __name__ == "__main__":
    unittest.main()
