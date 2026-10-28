---
name: rm-evaluate-scans
description: Evaluate the scans attached to the citations of one or more sources in the RootsMagic tree against the media details convention and the scan forms - flag caption, reference number, description, date, file name, folder, media type and shared rows with a script, review, decide, then fix media rows and rename files with dry runs and re-check.
argument-hint: "<source IDs or citation IDs>"
---

Evaluate scans: $ARGUMENTS

Follow CLAUDE.md throughout. The standards (M1-M4, G12, G13, G19, L1) and the "Scan forms" table are
in `scan_forms.md` (this folder): apply them without asking; ask only what they do not cover.
Item 8 of rm-record-cleanup step 5. Media rows and files are separate: `scripts/records/media.py`
changes rows, `scripts/files/file.py` changes files.

Flow as rm-evaluate-source: steps 0-3 read-only with every question asked up front (answers under
"Decisions" in `notes/issues/<type>_issues.md`); step 4 without further confirmation; issues at the end.

## 0. Working copy

`scripts/general/working_copy.py fetch`; after each apply, `push`.

## 1. Fetch and flag (script)

`scripts/media/evaluate_scans.py "tmp/work/Morton Tree.rmtree" --source ID` (or `--citation ID`).
Read `tmp/output/media/<timestamp>_evaluate_scans.txt`. Codes: M1 caption, M2 RefNumber, M3
description, M4 date, G13 file name, G19 unsure/Unsorted folder, L1 media type, SHARED (on several
citations), NOROW. `scripts/validate/validate_media.py` adds files missing on the drive, files not
in the tree and duplicate rows.

## 2. Review (judgement)

- Caption: the name as printed on the record (G12); a scan with two entries gets one media row per
  entry (SHARED).
- Description: the entry's summary from the saved reading, then where the image came from.
- G13: the new file name from the folder's naming (`rm-add-record`'s table); take the file's
  modified date (G16) before renaming: `scripts/files/file.py info "<path>"`.

## 3. Decisions (ask, all before step 4)

Standards apply without asking (M1-M4, G13, L1). Ask only, for example: a caption name that differs
between the record and the tree; a scan that may belong to another citation.

## 4. Fixes (dry run, apply; no confirmation)

| Fix | Command |
|---|---|
| Caption, RefNumber, Description | `scripts/records/media.py <tree> edit M --set Caption="..." --set RefNumber="..." --set Description="..."` |
| Date (SortDate follows) | `media.py <tree> edit M --date RM_DATE` |
| Media type (L1) | `media.py <tree> edit M --type 2` |
| Rename or move the file (G13) | `scripts/files/file.py rename "<path>" NEW_NAME` (or `move`), then `media.py <tree> edit M --path "<new path>"` for each row using it (`media.py <tree> get --path "<old path>"`) |
| One row per entry (SHARED) | `media.py <tree> create --path "<path>" --link citation:C` and `media.py <tree> edit M --unlink citation:C` |

Add `--apply` after checking each dry run.

## 5. Re-check, issues and finish

Re-run step 1: each flag left is a recorded decision or an issue (`notes/issues/<type>_issues.md`;
a task where a person is affected). Report counts per source, then the issues one at a time.
