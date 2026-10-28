---
name: rm-evaluate-quality
description: Evaluate the quality ratings of the citation links of one or more sources in the RootsMagic tree against the quality table - flag unrated links (with the expected rating), ratings that differ and links no rule covers, then set the ratings after the decisions, with dry runs and re-check.
argument-hint: "<source IDs or citation IDs>"
---

Evaluate quality ratings: $ARGUMENTS

Follow CLAUDE.md throughout. The ratings table is in `quality.md` (this folder): apply it without
asking; ask only what it does not cover. Item 9 of rm-record-cleanup step 5.

Flow as rm-evaluate-source: steps 0-3 read-only with every question asked up front (answers under
"Decisions" in `notes/issues/<type>_issues.md`); step 4 without further confirmation; issues at the end.

## 0. Working copy

`scripts/general/working_copy.py fetch`; after each apply, `push`.

## 1. Fetch and flag (script)

`scripts/citations/evaluate_quality.py "tmp/work/Morton Tree.rmtree" --source ID` (or `--citation ID`).
Read `tmp/output/citations/<timestamp>_evaluate_quality.txt`. Codes: UNRATED (with the expected
rating where a row fits), DIFFERS, NOROW.

## 2. Review (judgement)

- O or X: the table takes O where the source holds images and the citation has an image scan. A
  scan of a copy (e.g. a bishop's transcript) is X: check DIFFERS flags on image sources.
- Alternatives (`PDX|PIX`): which applies depends on who gave the information (e.g. the informant's
  own residence PDX, the other parent's PIX): read it from the saved reading.
- NOROW: agree the rating and add a row to `quality.md`.

## 3. Decisions (ask, all before step 4)

The table applies without asking where one rating fits. Ask only, for example: a fact or record
not in the table; a link whose alternative cannot be settled from the reading.

## 4. Fixes (dry run, apply; no confirmation)

`scripts/records/citation_link.py <tree> edit LINK_ID [LINK_ID ...] --quality XYZ`; links with the
same rating can be set in one command. Add `--apply` after checking the dry run.

## 5. Re-check, issues and finish

Re-run step 1: each flag left is a recorded decision or an issue (`notes/issues/<type>_issues.md`).
Report counts per source, then the issues one at a time.
