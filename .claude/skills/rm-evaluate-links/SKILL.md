---
name: rm-evaluate-links
description: Evaluate which facts the citations of one or more sources in the RootsMagic tree are linked to, against the facts each record type supports - flag missing links (naming the fact to link, or that it must be created), links to unsupported facts, record events or whole people, then link, unlink or create the facts after the decisions, with dry runs and re-check.
argument-hint: "<source IDs or citation IDs>"
---

Evaluate citation links: $ARGUMENTS

Follow CLAUDE.md throughout. The standards (G7, G8, G9, G17, G22, G23, G25, G37, G38, G39) and the
"Facts cited" table are in `facts_cited.md` (this folder): apply them without asking; ask only what
they do not cover. Items 3 (links) and 4 (new facts) of rm-record-cleanup step 5.

Flow as rm-evaluate-source: steps 0-3 read-only with every question asked up front (answers under
"Decisions" in `notes/issues/<type>_issues.md`); step 4 without further confirmation; issues at the end.

## 0. Working copy

`scripts/general/working_copy.py fetch`; after each apply, `push`.

## 1. Fetch and flag (script)

`scripts/citations/evaluate_links.py "tmp/work/Morton Tree.rmtree" --source ID [--source ID ...]`
(or `--citation ID`). Read `tmp/output/citations/<timestamp>_evaluate_links.txt`. Codes:

| Code | Meaning |
|---|---|
| MISSING | A required fact is not linked; per person: the event to link, or "create it (G8)" |
| EXTRA | Linked to a fact the record type does not support |
| G7 | Linked to a record event (removed with rm-remove-record-events) |
| G17 | Linked to a person as a whole |
| NOROW | No row fits: agree one and add it to `facts_cited.md` |

## 2. Review (judgement)

- MISSING with an event to link: check the event is the one the record bears on (date, place); a
  disagreement is still cited (G23) and gets a note on the event (G37), and goes to the issues.
- MISSING "create it": the fact comes from the record (G8). Dates: G9 (registration quarter or
  month: "before" the month after), G22 (from an age), G39 (census marriage); place from the
  record, as a place detail for an address (G21).
- EXTRA, G17: whether the record really shows that fact (keep and add a table row) or not (unlink).
- Conditional facts (e.g. Birth where an age is given) come from the transcription: use the saved
  readings, not the image.

## 3. Decisions (ask, all before step 4)

Standards apply without asking: link where the record supports the fact and the person's event
fits; create from the record where the person has none (G8) with the G9/G22 dates. Ask only, for
example: an event that does not fit the record; a fact or record type not in the table.

## 4. Fixes (dry run, apply; no confirmation)

| Fix | Command |
|---|---|
| Link | `scripts/records/citation_link.py <tree> create --citation C --owner event:E --quality ~~~` (`family:F`, `name:N`) |
| Unlink | `citation_link.py <tree> delete LINK_ID` |
| Create a fact | `scripts/records/event.py <tree> create --owner person:P --type N --date RM_DATE [--place L --site L]` then link it |
| Note on the event (G37) | `event.py <tree> edit E --set Note="..."` |

New links get `~~~` until rated (rm-evaluate-quality). Add `--apply` after checking each dry run.

## 5. Re-check, issues and finish

Re-run step 1: each flag left is a recorded decision or an issue. Open issues: a task linked to the
person (`scripts/records/task.py`), a note on the citation, a row in `notes/issues/<type>_issues.md`.
Report one short table per source, then the issues one at a time.
