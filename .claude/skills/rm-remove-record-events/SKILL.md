---
name: rm-remove-record-events
description: Remove record events (facts made for one record, FactTypeID 1000+) from the RootsMagic tree under G7 - a script says for each whether it is ready to delete, what must first be copied to the main fact (date, place, citations, media, description, note), or that it must be changed into the main fact; then copy, convert and delete with dry runs and re-check.
argument-hint: "<source IDs, record fact IDs, or event IDs>"
---

Remove record events: $ARGUMENTS

Follow CLAUDE.md throughout. G7 and the record fact -> main fact table are in `record_facts.md`
(this folder): apply them without asking; ask only what they do not cover. Item 6 of
rm-record-cleanup step 5.

Flow as rm-evaluate-source: steps 0-3 read-only with every question asked up front (answers under
"Decisions" in `notes/issues/<type>_issues.md`); step 4 without further confirmation; issues at the end.

## 0. Working copy

`scripts/general/working_copy.py fetch`; after each apply, `push`.

## 1. Fetch and evaluate (script)

`scripts/people/evaluate_record_events.py "tmp/work/Morton Tree.rmtree" --source ID` (or `--fact ID`,
`--event ID`, `--all`). Read `tmp/output/people/<timestamp>_evaluate_record_events.txt`:

| Status | Meaning |
|---|---|
| READY | Everything is on the main fact: delete |
| COPY | Copy what is listed (date, place, detail, citation, media, description, note) first |
| CONVERT | No matching main fact: change the record event into it (or, for a person's Marriage record, create the Marriage on the family) |
| DECIDE | No main fact agreed for this record fact: agree one and add it to `record_facts.md` |
| NOROW | No row fits the record fact |

## 2. Review (judgement)

- COPY of a description or note: whether it belongs on the main fact (G26: a description holds only
  that event's details; other text moves to its own fact) or is dropped.
- A date that differs from the main fact's: the evidence decides (G30, G31); a discrepancy gets a
  note on the event (G37).

## 3. Decisions (ask, all before step 4)

Standards apply without asking: copy date, place and citations to the main fact; convert where the
person has none; delete once everything is on the main fact. Ask only, for example: a record fact
with no main fact agreed; a description whose place is not clear.

## 4. Fixes (dry run, apply; no confirmation)

| Fix | Command |
|---|---|
| Copy date | `scripts/records/event.py <tree> edit MAIN --date RM_DATE` |
| Copy place | `event.py <tree> edit MAIN --place L [--site L]` |
| Copy description, note | `event.py <tree> edit MAIN --set Details="..."` / `--set Note="..."` |
| Copy a citation | `scripts/records/citation_link.py <tree> create --citation C --owner event:MAIN --quality XYZ` (the record event's rating) |
| Move a media link | `scripts/records/media.py <tree> edit M --link event:MAIN --unlink event:E` |
| Convert | `event.py <tree> edit E --type N` (N the main fact's FactTypeID) |
| Delete | `event.py <tree> delete E --with-links` (refused while media or witnesses remain) |

Add `--apply` after checking each dry run; re-run step 1 before deleting: the event must be READY.

## 5. Re-check, issues and finish

Re-run step 1: nothing left but recorded decisions and issues. Open issues: a task linked to the
person (`scripts/records/task.py`), a note on the citation, a row in `notes/issues/<type>_issues.md`.
Report counts per record fact, then the issues one at a time.
