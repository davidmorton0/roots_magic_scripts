import unittest

from evaluate_support import EvaluateTestCase

import evaluate_places


class EvaluatePlacesMainTest(EvaluateTestCase):
    def run_places(self, *args: str) -> tuple[int, str]:
        return self.run_main(evaluate_places.main, str(self.db), *args)

    def details(self) -> str:
        return self.output_path("evaluate_places", "places").read_text(encoding="utf-8")

    def test_all(self):
        code, out = self.run_places("--all")
        self.assertEqual(code, 0)
        self.assertIn("flags; DESC 1, MASTER 1, PLACE 1, SAME 1, SITE 1", out)
        details = self.details()
        for line in (
                "DESC E12 Birth: description 'at 4 Church Street' looks like an address",
                "SITE E12 Birth: place detail L2 '12 High Street' is under L1, not the event's place L6",
                "PLACE L4 '5 Mill Lane, Testham'",
                "MASTER L5 'Orphan'",
                "SAME under L1 'Testham, Kent, England': L2 '12 High Street', L3 '12, High Street'",
        ):
            self.assertIn(line, details)

    def test_source_scope(self):
        self.citations()
        code, out = self.run_places("--source", "1")
        self.assertEqual(code, 0)
        self.assertIn("4 events", out)
        self.assertNotIn("MASTER", self.details())


if __name__ == "__main__":
    unittest.main()
