import unittest

from support import ScriptTestCase

import find_person


class FindPersonMainTest(ScriptTestCase):
    def find(self, *args: str) -> str:
        code, out = self.run_main(find_person.main, str(self.db), *args)
        self.assertEqual(code, 0)
        return out

    def test_surname_only(self):
        out = self.find("--surname", "brown")
        self.assertIn("P2 Dr Mary Brown, 1860-?", out)
        self.assertIn("P3 Albert Brown, Jr, ?-?", out)
        self.assertIn("2 found", out)

    def test_given_name_start(self):
        out = self.find("--surname", "Brown", "--given", "Al")
        self.assertIn("P3 Albert Brown", out)
        self.assertIn("1 found", out)

    def test_alternative_name(self):
        out = self.find("--surname", "Brownley", "--given", "Bert")
        self.assertIn("P3 Albert Brown, Jr, ?-? (as Bert Brownley)", out)

    def test_pattern_and_no_match(self):
        self.assertIn("2 found", self.find("--surname", "Brown%"))  # P3 matches as Brown and as Brownley
        self.assertIn("0 found", self.find("--surname", "Smith", "--given", "Mary"))

    def test_does_not_change_database(self):
        before = self.db.read_bytes()
        self.find("--surname", "smith")
        self.assertEqual(self.db.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
