---
name: rm-check
description: Check the RootsMagic .rmtree database for issues, one validation script per record type (sources, citations, citation links, media and scan files, people, names, events, families, places, tasks), and list the records affected. Read-only.
argument-hint: "[path-to-rmtree] [record types, e.g. media person] [--no-scans]"
allowed-tools: Bash(mise exec -- python ${CLAUDE_PROJECT_DIR}/scripts/validate/validate_*.py *)
---

Run the database checks and report the results. Read-only: never change the database.

Arguments: $ARGUMENTS
- First argument: path to the .rmtree file. If none is given, ask which file to use (for example
  `tmp/work/Morton Tree.rmtree`, the working copy).
- Record types: run only those scripts; none given, run all ten.
- `--no-scans`: skip the media checks that compare the database with the scan files on disk.

Run, from the project root, one command per record type (each is read-only):

```bash
mise exec -- python ${CLAUDE_PROJECT_DIR}/scripts/validate/validate_<type>.py "<path>"
```

`<type>`: source, citation, citation_link, media, person, name, event, family, place, task.
`validate_media.py` also takes `--no-scans` (or `--scan-list FILE`); it lists the scan files through
Windows PowerShell (the H: drive is not visible from WSL). Each script prints a count per check and
writes every affected record to `tmp/output/validate/<YYYYMMDD_HHMMSS>_validate_<type>.txt`.
Settings (scan folder, folders to skip, age limits) are in `config.toml`, or `config.example.toml`
if that is missing.

Report:
1. One summary table: record type, check, count, title; non-zero first.
2. The paths of the report files.
3. Only if asked: the records for a given check, read from its report file (section header
   `== <code>: ...`).

Record IDs in the reports: P person, F family, E event, C citation, S source, M media, N name,
L place, T task. Dates show as YYYY-MM-DD when exact; otherwise in RootsMagic's raw form.

To add a check: a function in the record type's `scripts/validate/validate_<type>.py` with the
`@CHECKS.add(code, title)` decorator returning one line per record (shared loading in
`validate_common.py`), and a case in the fixture and expected counts of `tests/test_validate_<type>.py`
(fixture in `tests/validate_support.py`).
