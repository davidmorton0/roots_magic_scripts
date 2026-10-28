import unittest

from evaluate_support import EvaluateTestCase

import evaluate_scans

TABLE = """# Test

## Scan forms

| Scans | Name | Caption | RefNumber | Description | File |
|---|---|---|---|---|---|
| Birth index image | `Birth Register - UK - *` | `*, * – birth index – * Q*` | `* Q* * * *` | `Births registered in *` | `*-BRG-*` |
"""
DATE = "D.+18500101..+00000000.."


class EvaluateScansMainTest(EvaluateTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.table.write_text(TABLE, encoding="utf-8")
        self.citations()
        self.add("INSERT INTO MultimediaTable VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
            (1, 1, "H:\\Records\\Births", "DOE-J-BRG-1850-Q1.jpg", "Doe, John – birth index – 1850 Q1",
             "1850 Q1 Testham 5 12", "Births registered in January, February, and March 1850: John Doe", DATE),
            (2, 1, "H:\\Records\\Births\\unsure", "DOE_T.pdf", "Doe, Tom – birth index – 1851 Q1", "", "", "."),
            (3, 2, "H:\\Records\\Burials", "DOE-J-BIB-1910.jpg", "Doe, John – burial – 1910", "", "x", DATE),
        ])
        self.add("INSERT INTO MediaLinkTable VALUES (?, ?, ?, ?)",
                 [(1, 1, 4, 20), (2, 2, 4, 21), (3, 2, 4, 24), (4, 3, 4, 22)])

    def run_scans(self, *args: str) -> tuple[int, str]:
        return self.run_main(evaluate_scans.main, str(self.db), "--table", str(self.table), *args)

    def details(self) -> str:
        return self.output_path("evaluate_scans", "media").read_text(encoding="utf-8")

    def test_flags(self):
        code, out = self.run_scans("--all")
        self.assertEqual(code, 0)
        self.assertIn("S1 'Birth Register - UK - TestBMD': 2 scans, 1 flagged", out)
        details = self.details()
        for line in (
                "M2 RefNumber is empty", "M3 Description is empty", "M4 no Date",
                "G13 file name 'DOE_T.pdf' not in the form '*-BRG-*'", "G19 file in an unsure or Unsorted folder",
                "L1 .pdf stored as Image", "SHARED on citations C21, C24", "NOROW no row in scan_forms.md",
                "M1 caption year 1910, Date year 1850",
        ):
            self.assertIn(line, details)
        self.assertNotIn("M1  H:\\Records\\Births\\DOE-J", details)

    def test_citation_and_none(self):
        code, _ = self.run_scans("--citation", "20")
        self.assertIn("(no flags)", self.details())
        self.assertEqual(self.run_scans("--citation", "99")[0], 1)

    def test_skill_table(self):
        rows = evaluate_scans.load_rows(evaluate_scans.TABLE_FILE, "Scan forms")
        self.assertGreater(len(rows), 15)


if __name__ == "__main__":
    unittest.main()
