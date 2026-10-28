import unittest

from evaluate_support import EvaluateTestCase

import evaluate_links

TABLE = """# Test

## Facts cited

| Record type | Name | Condition | Required | Optional |
|---|---|---|---|---|
| Birth index | `Birth Register - UK - *` | - | Birth | Death if SpecificItem~age , name |
| Burial | `Burials - *` | SpecificItem~^burial | Burial | Death, Birth |
"""


class EvaluateLinksMainTest(EvaluateTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.table.write_text(TABLE, encoding="utf-8")
        self.citations()

    def run_links(self, *args: str) -> tuple[int, str]:
        return self.run_main(evaluate_links.main, str(self.db), "--table", str(self.table), *args)

    def details(self) -> str:
        return self.output_path("evaluate_links", "citations").read_text(encoding="utf-8")

    def test_flags(self):
        code, out = self.run_links("--source", "1", "--source", "2", "--source", "3")
        self.assertEqual(code, 0)
        self.assertIn("S1 'Birth Register - UK - TestBMD': 3 citations, 3 flagged", out)
        details = self.details()
        for line in (
                "G7 linked to record event E14 (Directory)",
                "G17 linked to person P3 Tom Doe as a whole",
                "MISSING Burial: P1 John Doe: no Burial - create it (G8)",
                "MISSING Birth: P1 John Doe: E10",
                "NOROW no row in facts_cited.md fits this citation",
        ):
            self.assertIn(line, details)
        self.assertNotIn("EXTRA linked to Directory", details)

    def test_extra_and_conditional(self):
        self.add("INSERT INTO CitationLinkTable (LinkID, CitationID, OwnerType, OwnerID, Quality) VALUES (?, ?, ?, ?, ?)",
                 [(9, 20, 2, 13, "PDX")])
        code, _ = self.run_links("--citation", "20", "--citation", "21", "--citation", "24")
        details = self.details()
        self.assertIn("MISSING Death: P3 Tom Doe: no Death - create it (G8)", details)
        self.assertIn("EXTRA linked to Residence (1), not a fact 'Birth index' supports", details)
        self.assertIn("MISSING Birth: P1 John Doe: E10 (D.+18500101..+00000000..) - link it", details)
        self.assertNotIn("EXTRA linked to Death", details)

    def test_missing_ids_and_table(self):
        self.assertEqual(self.run_links("--source", "99")[0], 1)
        rows = evaluate_links.load_rows(evaluate_links.TABLE_FILE, "Facts cited")
        self.assertGreater(len(rows), 10)
        self.assertEqual(evaluate_links.parse_facts("Birth if SpecificItem~(age |born ), name"),
                         [("Birth", "SpecificItem~(age |born )"), ("name", "")])


if __name__ == "__main__":
    unittest.main()
