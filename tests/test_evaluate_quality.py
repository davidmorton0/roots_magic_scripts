import unittest

from evaluate_support import EvaluateTestCase

import evaluate_quality

TABLE = """# Test

## Ratings

| Record | Name | Fact | Condition | Rating |
|---|---|---|---|---|
| Birth index | `Birth Register - UK - *` | Birth | - | PIX |
| Birth index | `Birth Register - UK - *` | Death | SpecificItem~age | SIX\\|SDX |
| Burial | `Burials - *` | Burial\\|Death | - | PD{O/X} |
"""


class EvaluateQualityMainTest(EvaluateTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.table.write_text(TABLE, encoding="utf-8")
        self.citations()

    def run_quality(self, *args: str) -> tuple[int, str]:
        return self.run_main(evaluate_quality.main, str(self.db), "--table", str(self.table), *args)

    def details(self) -> str:
        return self.output_path("evaluate_quality", "citations").read_text(encoding="utf-8")

    def test_flags(self):
        code, out = self.run_quality("--all")
        self.assertEqual(code, 0)
        details = self.details()
        self.assertIn("C21 L2 -> Birth 12: UNRATED expected PIX (Birth index)", details)
        self.assertIn("C21 L3 -> person 3: NOROW PIX", details)
        self.assertIn("C24 L7 -> Death 11: NOROW PIX", details)
        self.assertNotIn("L1 ", details)
        self.assertIn("C22 L5 -> Newspaper Article 16: NOROW PDO", details)
        self.assertIn("S2 'Burials - England - Testham - Ancestry': 2 links, 1 flagged", out)

    def test_image_rule_needs_an_image_scan(self):
        self.add("INSERT INTO MultimediaTable (MediaID, MediaFile) VALUES (?, ?)", [(1, "x.jpg")])
        self.add("INSERT INTO MediaLinkTable VALUES (?, ?, ?, ?)", [(1, 1, 4, 22)])
        code, out = self.run_quality("--source", "2")
        self.assertIn("C22 L4 -> Death 11: DIFFERS PDX; expected PDO (Burial)", self.details())

    def test_missing(self):
        self.assertEqual(self.run_quality("--citation", "99")[0], 1)
        rows = evaluate_quality.load_rows(evaluate_quality.TABLE_FILE, "Ratings")
        self.assertGreater(len(rows), 30)


if __name__ == "__main__":
    unittest.main()
