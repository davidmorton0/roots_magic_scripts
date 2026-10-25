import shutil
import unittest
from pathlib import Path
from unittest import mock

from support import ScriptTestCase

import working_copy


class WorkingCopyMainTest(ScriptTestCase):
    """The 'Windows' test tree is a local file; PowerShell calls are replaced by local ones."""

    def setUp(self) -> None:
        super().setUp()
        self.test_tree = self.tmp / "windows" / "test.rmtree"
        self.test_tree.parent.mkdir()
        self.test_tree.write_bytes(b"tree v1")
        self.config = self.tmp / "config.toml"
        self.config.write_text(f"test_tree = '{self.test_tree}'\nworking_copy = \"work/tree.rmtree\"\n")
        self.work = self.tmp / "work" / "tree.rmtree"
        self.running = False
        for name, value in (
            ("PROJECT_DIR", self.tmp),
            ("rootsmagic_running", lambda: self.running),
            ("windows_file_hash", lambda p: working_copy.file_hash(Path(p))),
            ("copy_windows_file", lambda s, t: shutil.copyfile(s, t)),
            ("windows_path", lambda p: str(p)),
        ):
            patcher = mock.patch.object(working_copy, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def call(self, action: str) -> tuple[int, str]:
        return self.run_main(working_copy.main, action, "--config", str(self.config))

    def test_fetch_then_push(self):
        code, out = self.call("fetch")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.work.read_bytes(), b"tree v1")
        self.work.write_bytes(b"tree v2")
        code, out = self.call("push")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.test_tree.read_bytes(), b"tree v2")
        self.assertIn("hashes match", out)

    def test_push_refused_when_test_tree_changed(self):
        self.call("fetch")
        self.test_tree.write_bytes(b"saved by RootsMagic")
        self.work.write_bytes(b"tree v2")
        code, out = self.call("push")
        self.assertEqual(code, 1)
        self.assertIn("changed since the last fetch or push", out)
        self.assertEqual(self.test_tree.read_bytes(), b"saved by RootsMagic")

    def test_refused_while_rootsmagic_runs(self):
        self.running = True
        code, out = self.call("fetch")
        self.assertEqual(code, 1)
        self.assertIn("RootsMagic is running", out)
        self.assertFalse(self.work.exists())

    def test_status_changes_nothing(self):
        code, out = self.call("status")
        self.assertEqual(code, 0)
        self.assertIn("recorded:     None", out)
        self.assertFalse(self.work.exists())


if __name__ == "__main__":
    unittest.main()
