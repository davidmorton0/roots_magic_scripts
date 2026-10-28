---
name: rm-evaluate-citation
description: Evaluate the citations of one or more sources in the RootsMagic tree against the citation standards and forms - flag with a script (fields, CitationName, AccessDate, transcription layout, FreeBMD link, duplicates, shared scans), review, ask the decisions the standards do not cover, then fix with dry runs and re-check.
argument-hint: "<source IDs or citation IDs>"
---

Evaluate citations: $ARGUMENTS

Follow CLAUDE.md throughout. The citation standards (G10, G11, G12, G14, G16, C1-C4) and the
"Citation forms" table are in `.claude/skills/rm-evaluate-source/source_types.md`: apply them
without asking; ask only what they do not cover. Item 2 of rm-record-cleanup step 5.

Flow as rm-evaluate-source: steps 0-3 read-only with every question asked up front (answers under
"Decisions" in `notes/issues/<type>_issues.md`); step 4 without further confirmation; issues at the end.

## 0. Working copy

`scripts/general/working_copy.py fetch`; after each apply, `push`.

## 1. Fetch and flag (script)

`scripts/citations/evaluate_citation.py "tmp/work/Morton Tree.rmtree" --source ID [--source ID ...]`
(or `--citation ID`). Read `tmp/output/citations/<timestamp>_evaluate_citation.txt`. Codes: FORM,
EMPTY, C1 (CitationName), G16 (AccessDate empty with a scan), C3 (AccessDate form), G10
(transcription), C2 (line ends), LAST (last line, the FreeBMD link), G11 (same entry), G12 (shared
scan and person), UNUSED.

## 2. Review (judgement)

- G11, G12: whether two citations are the same record (merge) or different entries (keep, record it).
- FORM, EMPTY, G10: the right values come from the record: use the saved readings
  (`notes/<type>_readings.md`); read a scan only where they lack something, once (user's rule).
- LAST: the FreeBMD link is supplied by the user (FreeBMD blocks automated access); C4 asks for it
  on new or completed citations only.
- G16: with a scan, the file's modified date (`scripts/files/file.py info "<path>"`), read before any
  rename or move; with none, the date in the transcription's citation text, otherwise left empty.

## 3. Decisions (ask, all before step 4)

Standards apply without asking: C1 (rebuild the name), C2 (CR LF), C3 (date form), G16 from the
file date, a field brought to its form when the record gives the value. Ask only, for example:
which of two duplicates is kept; a value the record does not settle; FreeBMD links wanted now or later.

## 4. Fixes (dry run, apply; no confirmation)

| Fix | Command |
|---|---|
| Field (rebuilds CitationName) | `scripts/records/citation.py <tree> edit ID --field Name=Value` |
| CitationName only | `citation.py <tree> edit ID --field Name=<its own value>` |
| Transcription (CR LF written) | `citation.py <tree> edit ID --text-file FILE` (file in `tmp/`) |
| Note | `citation.py <tree> edit ID --set Comments="..."` |
| Merge duplicates on one record | `scripts/citations/merge_duplicate_citations.py` |
| Delete (links too) | `citation.py <tree> delete ID --with-links` (refused while scans are attached) |

Add `--apply` after checking each dry run against the decisions; a refused dry run stops the work.

## 5. Re-check, issues and finish

Re-run step 1: each flag left is a recorded decision or an issue. Open issues (item 10): a task
linked to the person (`scripts/records/task.py <tree> create --name ... --details ... --person ID`),
a note on the affected citation pointing to it, and a row under "Issues" in
`notes/issues/<type>_issues.md`. Report one short table per source, then the issues one at a time.
