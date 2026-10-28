---
name: rm-evaluate-source
description: Evaluate one or more sources in the RootsMagic tree against the source standards and the source-type table - fetch each source's data and flag what does not fit with a script, review the flags, ask the decisions the standards do not cover, then fix the source rows (name, fields, text, comments, layout, merge, delete) with dry runs and re-check.
argument-hint: "<source IDs, e.g. 583 589>, or 'all'"
---

Evaluate sources: $ARGUMENTS

Follow CLAUDE.md throughout (safety rules, working files, database notes, conventions). The
standards and the source-type table are in `source_types.md` (this folder): apply them without
asking; ask only what they do not cover. This skill works on source rows only. Citations, links,
scans and facts belong to the record type's clean-up (rm-record-cleanup).

## Flow

1. **Questions up front.** Steps 0-3 are read-only. Collect every question the fixes depend on
   and ask them before any change, one at a time, each with labelled options and what each does.
   Record each answer under "Decisions" in `notes/issues/source_issues.md` as it is given.
2. **Fixes without further confirmation.** The answers are the approval. Run step 4 from start to
   finish: each change has a dry run, checked against the decisions, then is applied.
3. **Issues at the end.** Anything found during the fixes that the decisions do not cover is left
   unchanged and noted under "Issues" in `notes/issues/source_issues.md`, then presented one at a time.

## 0. Working copy

`scripts/general/working_copy.py fetch` (checks RootsMagic is closed). After each apply,
`working_copy.py push`; if refused, fetch again, re-run the dry run, apply, push.

## 1. Fetch and flag (script)

`scripts/sources/evaluate_source.py "tmp/work/Morton Tree.rmtree" --source ID [--source ID ...]`
(or `--all` for every source, which prints counts per flag). It matches each source to a source
type and writes, per source, its template, citations, links, scans, fields, text, comments and
flags to `tmp/output/sources/<timestamp>_evaluate_source.txt`. Read that file. Flag codes:

| Code | Meaning | Standard |
|---|---|---|
| TYPE | No source type matches the name | Table |
| G1 | Template differs from the type's (no type: neither 0 nor 6) | G1 |
| G2 | Name not "<Record> - <Country> - <Provider>", unknown country, stray spaces | G2 |
| G3 | Another source with the same name, or the same database and website title | G3 |
| G4 | Source text empty or holding a URL; comments not empty | G4 |
| G18 | Template 6 with scans in a Newspaper folder | G18 |
| L1 | Fields saved with a byte-order mark or XML declaration | L1 |
| L2 | A required source field empty; DatabaseCreator filled | L2, Required column |
| L3 | No citations | L3 |
| FIXED | A field differs from the type's fixed value | Fixed column |
| TEXT | Source text differs from the type's text | Text column |

## 2. Review (judgement)

The script flags what it can measure; these need reading:

- **TYPE**: which type the source is. If a row fits, the source may only need renaming; if none
  does, agree a new row (name pattern, template, required and fixed fields) and add it to
  `source_types.md` before fixing. No real names in that file.
- **G1**: whether the source is an online database (6) or a document such as a certificate (0).
  A template change also changes every citation's fields: it is not a source fix here. Note it
  as an issue for the record type's clean-up (a conversion script per type, rewriting each citation's fields).
- **G2**: the name says what the record is (G2); check the proposed name against the type's pattern.
- **G3**: whether two sources are the same database. Same: merge (step 4). Different: keep both;
  record the decision so the flag is expected next time.
- **G4**: whether a comment is pasted website text (cleared) or a note worth keeping (kept,
  recorded). Draft any missing source text in the style of the type's existing sources: what the
  record is, who made it, where it was viewed, "(text only)" for indexes without images.
- **G5**: compare WebsiteCreator and DatabaseTitle with the saved page, where the user has one;
  the script does not check this.
- **G18, G6**: whether a newspaper or another site is the real source. These move citations:
  note them as issues for the record type's clean-up.

## 3. Decisions (ask, all before step 4)

Standing standards apply without asking: L1, L2 and the type's Fixed and Text values (set the
field to the value), a URL removed from the source text, a name brought to the type's pattern
when the record and provider are clear. Ask only, for example:

1. A source with no type: which type, and the new table row.
2. G3 candidates: merge or keep apart (and which source is kept).
3. L3: delete the unused source or keep it.
4. A comment that may be a real note: clear or keep.
5. New source text or name where the wording is not given by the type.

## 4. Fixes (dry run, apply; no confirmation)

Every change through a script with a dry run, applied to the working copy, then pushed. One
source row per command.

| Fix | Command |
|---|---|
| Rename | `scripts/records/source.py <tree> edit ID --name "NEW NAME"` |
| Source field (template's source fields; Footnote, ShortFootnote, Bibliography for free-form) | `source.py <tree> edit ID --field Name=Value [--field ...]` |
| Empty a field (e.g. DatabaseCreator) | `source.py <tree> edit ID --field DatabaseCreator=` |
| Source text, comments | `source.py <tree> edit ID --set ActualText="..."`, `--set Comments=` |
| L1 layout | any `--field` edit rewrites Fields without the declaration; with nothing else to change, set one field to its own value |
| Merge (G3) | `scripts/sources/split_source.py <tree> --from DROP --match "" --to KEEP` (moves every citation; both must have the same template), then `source.py <tree> delete DROP` |
| Delete (L3) | `source.py <tree> delete ID` (refused while anything still uses it) |

Add `--apply` after checking the dry run against the decisions. A refused or failing dry run
stops the work: report it and wait (CLAUDE.md). Names and Fields are in RMNOCASE indexes: the user
runs RootsMagic's rebuild indexes when next opening the tree.

## 5. Re-check and finish

1. Re-run step 1 on the same sources. Each flag left must be a recorded decision ("kept apart",
   "comment kept") or an issue; anything else is a fix missed.
2. Report one short table: source, flags before, fixes made, flags left and why.
3. Then the issues, one at a time. Issues for a record type's clean-up (template change, G6,
   G18) also go into that type's `notes/issues/<type>_issues.md`.
