import unittest

from support import ScriptTestCase

import people


class PeopleMainTest(ScriptTestCase):
    def test_writes_everyone_to_timestamped_file(self):
        code, out = self.run_main(people.main, str(self.db))

        path = self.output_path("people")
        self.assertEqual(code, 0)
        self.assertEqual(out, f"Output written to: {path}\n4 people\n")
        self.assertEqual(
            path.read_text(encoding="utf-8").splitlines(),
            [
                "   ID  Sex  Born  Died  Name",
                "    4    1              (no primary name)",
                "    3    0              Albert Brown, Jr",
                "    2    1  1860        Dr Mary Brown",
                "    1    0  1850  1910  John smith",
                "",
                "4 people",
            ],
        )

    def test_does_not_change_database(self):
        before = self.db.read_bytes()
        self.run_main(people.main, str(self.db))
        self.assertEqual(self.db.read_bytes(), before)

    def test_missing_file(self):
        code, out = self.run_main(people.main, str(self.tmp / "nope.rmtree"))
        self.assertEqual(code, 2)
        self.assertIn("File not found", out)
        self.assertFalse(self.output_dir.exists())

    def test_no_arguments_prints_usage(self):
        code, out = self.run_main(people.main)
        self.assertEqual(code, 2)
        self.assertIn("Usage: python people.py", out)


if __name__ == "__main__":
    unittest.main()
