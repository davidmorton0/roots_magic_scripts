import unittest

from support import ScriptTestCase

import schema


class SchemaMainTest(ScriptTestCase):
    def test_full_report_goes_to_timestamped_file(self):
        code, out = self.run_main(schema.main, str(self.db))

        path = self.output_path("schema")
        self.assertEqual(code, 0)
        self.assertEqual(out, f"Output written to: {path}\n")
        text = path.read_text(encoding="utf-8")
        self.assertIn("Tables: 2", text)
        self.assertIn("== NameTable  (4 rows)", text)
        self.assertIn("== PersonTable  (4 rows)", text)
        self.assertIn("INDEX idxSurname (Surname COLLATE RMNOCASE)", text)
        self.assertIn("== views: 0", text)
        self.assertIn("== triggers: 0", text)

    def test_named_tables_are_printed_not_saved(self):
        code, out = self.run_main(schema.main, str(self.db), "persontable")

        self.assertEqual(code, 0)
        self.assertIn("== PersonTable  (4 rows)", out)
        self.assertNotIn("NameTable", out)
        self.assertFalse(self.output_dir.exists())

    def test_unknown_table_is_reported(self):
        code, out = self.run_main(schema.main, str(self.db), "Nope", "NameTable")

        self.assertEqual(code, 0)
        self.assertIn("Tables not found: Nope", out)
        self.assertIn("== NameTable  (4 rows)", out)

    def test_does_not_change_database(self):
        before = self.db.read_bytes()
        self.run_main(schema.main, str(self.db))
        self.assertEqual(self.db.read_bytes(), before)

    def test_missing_file(self):
        code, out = self.run_main(schema.main, str(self.tmp / "nope.rmtree"))
        self.assertEqual(code, 2)
        self.assertIn("File not found", out)

    def test_no_arguments_prints_usage(self):
        code, out = self.run_main(schema.main)
        self.assertEqual(code, 2)
        self.assertIn("Usage: python schema.py", out)


if __name__ == "__main__":
    unittest.main()
