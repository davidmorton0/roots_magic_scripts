import sqlite3
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from support import ScriptTestCase

import list_scans

EXAMPLE_CONFIG = Path(__file__).resolve().parent.parent / "config.example.toml"
FOLDER = "H:\\My Drive\\Records\\Marriage - Church\\Britain"
FILES = [
    (f"{FOLDER}\\Images\\SMI.J-BRO.M-MCIB-1880.jpg", date(2019, 1, 26)),
    (f"{FOLDER}\\Images\\NEW.A-MCIB-1890.jpg", date(2020, 9, 9)),
    (f"{FOLDER}\\Images\\unsure\\X.jpg", date(2020, 1, 1)),
    (f"{FOLDER}\\Unsorted\\Y.jpg", date(2020, 1, 1)),
]


class ListScansMainTest(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        patcher = mock.patch.object(list_scans, "list_windows_files_with_dates", return_value=FILES)
        self.lister = patcher.start()
        self.addCleanup(patcher.stop)
        conn = sqlite3.connect(self.db)
        conn.execute("CREATE TABLE MultimediaTable (MediaID INTEGER PRIMARY KEY, MediaPath TEXT, MediaFile TEXT)")
        conn.execute("INSERT INTO MultimediaTable VALUES (5, ?, 'SMI.J-BRO.M-MCIB-1880.jpg')", (f"{FOLDER}\\Images",))
        conn.commit()
        conn.close()

    def test_lists_files_with_dates_skipping_unsure_and_unsorted(self):
        code, out = self.run_main(list_scans.main, "Marriage - Church\\Britain", "--config", str(EXAMPLE_CONFIG))
        self.assertEqual(code, 0)
        self.lister.assert_called_once_with(FOLDER)
        self.assertIn("   Images\\NEW.A-MCIB-1890.jpg  9 September 2020\n", out)
        self.assertIn("   Images\\SMI.J-BRO.M-MCIB-1880.jpg  26 January 2019\n", out)
        self.assertNotIn("X.jpg", out)
        self.assertNotIn("Y.jpg", out)
        self.assertIn("2 files", out)

    def test_tree_shows_media_rows(self):
        code, out = self.run_main(list_scans.main, FOLDER, "--tree", str(self.db), "--config", str(EXAMPLE_CONFIG))
        self.assertEqual(code, 0)
        self.assertIn("SMI.J-BRO.M-MCIB-1880.jpg  26 January 2019  M5", out)
        self.assertIn("NEW.A-MCIB-1890.jpg  9 September 2020  not in the tree", out)


if __name__ == "__main__":
    unittest.main()
