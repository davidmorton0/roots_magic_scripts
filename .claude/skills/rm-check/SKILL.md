---
name: rm-check
description: Check the RootsMagic .rmtree database for issues (scans not attached to citations, missing files, missing dates/places/citations, events dated wrongly, people and families with gaps) and list the records affected. Read-only.
argument-hint: "[path-to-rmtree] [--no-scans]"
allowed-tools: Bash(mise exec -- python ${CLAUDE_PROJECT_DIR}/scripts/general/check.py *)
---

Run the database checks and report the results. Read-only: never change the
database.

Arguments: $ARGUMENTS
- First argument: path to the .rmtree file. If none is given, ask which file to
  use (for example `tmp/work/Morton Tree.rmtree`, the working copy).
- `--no-scans`: skip the checks that compare the database with the scan files on disk.

Run, from the project root:

```bash
mise exec -- python ${CLAUDE_PROJECT_DIR}/scripts/general/check.py "<path>" [--no-scans]
```

The script lists the scan files through Windows PowerShell (the H: drive is not
visible from WSL), prints a count per check, and writes every affected record to
`tmp/output/general/<YYYYMMDD_HHMMSS>_check.txt`. Settings (scan folder, folders to
skip, age limits) are in `config.toml`, or `config.example.toml` if that is missing.

Report:
1. The summary table: count and title per check, non-zero first.
2. Path of the report file.
3. Only if asked: the records for a given check, read from the report file
   (section header `== <code>: ...`).

Record IDs in the report: P person, F family, E event, C citation, S source,
M media. Dates show as YYYY-MM-DD when exact; otherwise in RootsMagic's raw form.

To add a check: write a function in `scripts/general/check.py` with the `@check(code,
title)` decorator returning one line per record, and add it to the fixture and
`EXPECTED_COUNTS` in `tests/test_check.py`.
