import sqlite3
import unittest
from datetime import date
from unittest import mock

from support import ScriptTestCase

import rename_scan

FOLDER = "H:\\My Drive\\Records\\Deaths\\Britain\\Registers"
OLD = f"{FOLDER}\\DOE-J-DRB-1905-Q2.jpg"
NEW = "DOE-J-DRB-1905-Q3.jpg"


class RenameScanMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        conn = sqlite3.connect(self.db)
        conn.executescript("""
            CREATE TABLE MultimediaTable (MediaID INTEGER PRIMARY KEY, MediaPath TEXT,
                MediaFile TEXT, UTCModDate FLOAT);
        """)
        conn.executemany("INSERT INTO MultimediaTable VALUES (?, ?, ?, 1.0)", [
            (1, FOLDER, "DOE-J-DRB-1905-Q2.jpg"),
            (2, FOLDER, "doe-j-drb-1905-q2.jpg"),  # a second row for the same file
            (3, FOLDER, "OTHER.jpg"),
        ])
        conn.commit()
        conn.close()
        self.files = {OLD.lower()}
        for name, fake in (("windows_file_modified", self.modified), ("rename_windows_file", self.rename),
                           ("move_windows_file", self.move)):
            patcher = mock.patch.object(rename_scan, name, side_effect=fake)
            self.addCleanup(patcher.stop)
            setattr(self, name, patcher.start())

    def modified(self, path: str) -> date | None:
        return date(2020, 1, 1) if path.lower() in self.files else None

    def rename(self, path: str, new: str) -> None:
        self.files.remove(path.lower())
        self.files.add(f"{path.rpartition(chr(92))[0]}\\{new}".lower())

    def move(self, path: str, new_path: str) -> None:
        self.files.remove(path.lower())
        self.files.add(new_path.lower())

    def media_files(self) -> list[tuple]:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT MediaID, MediaFile FROM MultimediaTable ORDER BY MediaID").fetchall()
        finally:
            conn.close()

    def test_apply_moves_file_to_another_folder(self):
        target = "H:\\My Drive\\Records\\Deaths\\Britain\\Banns\\DOE-J-DBB-1905.jpg"
        code, out = self.run_main(rename_scan.main, str(self.db), "--rename", OLD, target, "--apply")

        self.assertEqual(code, 0, out)
        self.move_windows_file.assert_called_once_with(OLD, target)
        self.rename_windows_file.assert_not_called()
        conn = sqlite3.connect(self.db)
        try:
            rows = conn.execute("SELECT MediaPath, MediaFile FROM MultimediaTable WHERE MediaID IN (1, 2)").fetchall()
        finally:
            conn.close()
        self.assertEqual(rows, [("H:\\My Drive\\Records\\Deaths\\Britain\\Banns", "DOE-J-DBB-1905.jpg")] * 2)

    def test_dry_run_changes_nothing(self):
        before = self.db.read_bytes()
        code, out = self.run_main(rename_scan.main, str(self.db), "--rename", OLD, NEW)

        self.assertEqual(code, 0)
        self.assertIn(f"{OLD} -> {NEW} (media M1, M2)\nDry run: nothing changed.", out)
        self.assertEqual(self.db.read_bytes(), before)
        self.rename_windows_file.assert_not_called()

    def test_apply_renames_file_and_rows(self):
        code, out = self.run_main(rename_scan.main, str(self.db), "--rename", OLD, NEW, "--apply")

        self.assertEqual(code, 0)
        self.assertIn("Applied: 1 files and 2 media rows renamed.", out)
        self.rename_windows_file.assert_called_once_with(OLD, NEW)
        self.assertEqual(self.media_files(), [(1, NEW), (2, NEW), (3, "OTHER.jpg")])

    def test_refused_when_new_name_exists(self):
        self.files.add(f"{FOLDER}\\{NEW}".lower())
        code, out = self.run_main(rename_scan.main, str(self.db), "--rename", OLD, NEW, "--apply")

        self.assertEqual(code, 1)
        self.assertIn(f"already exists: {FOLDER}\\{NEW}", out)
        self.rename_windows_file.assert_not_called()

    def test_failed_rename_rolls_back(self):
        second = f"{FOLDER}\\OTHER.jpg"
        self.files.add(second.lower())

        def rename(path, new):
            if path == second:
                raise RuntimeError("locked")
            self.rename(path, new)

        self.rename_windows_file.side_effect = rename
        with self.assertRaises(RuntimeError):
            self.run_main(rename_scan.main, str(self.db), "--rename", OLD, NEW,
                          "--rename", second, "OTHER2.jpg", "--apply")
        self.assertEqual(self.media_files()[0], (1, "DOE-J-DRB-1905-Q2.jpg"))
        self.assertIn(OLD.lower(), self.files)

    def test_no_arguments_prints_usage(self):
        code, out = self.run_main(rename_scan.main)
        self.assertEqual(code, 2)
        self.assertIn("Usage: python rename_scan.py", out)


if __name__ == "__main__":
    unittest.main()
