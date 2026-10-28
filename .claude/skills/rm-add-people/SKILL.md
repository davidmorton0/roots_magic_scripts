---
name: rm-add-people
description: Add the people a record names to the RootsMagic tree where the standards say so (parents, spouses, children and others whose relationship to someone in the tree is stated), with their names, families, a Birth from the age and the record cited on their facts - judgement from the saved readings, then person, name, family, event and link scripts with dry runs.
argument-hint: "<source ID or citation IDs>"
---

Add people named on records: $ARGUMENTS

Follow CLAUDE.md throughout and the standing decisions in
`.claude/skills/rm-record-cleanup/source_standards.md`. Item 5 of rm-record-cleanup step 5. There
is no flagging script: who a record names, and how they relate, is read from the record.

Flow as rm-evaluate-source: steps 0-2 read-only with every question asked up front (answers under
"Decisions" in `notes/issues/<type>_issues.md`); step 3 without further confirmation; issues at the end.

## Standards (from source_standards.md)

| # | Standard |
|---|---|
| G22 | A Birth known only from an age: "between" the month after the event's month, age + 1 years earlier, and the event's month, age years earlier |
| G27 | Informants with no stated relationship: matched to the deceased's household or immediate family; exactly one person of that name there is the informant; otherwise transcription only |
| G28 | A person whose relationship to someone in the tree cannot be clearly established is not added: transcription only, without a question |
| G29 | Parents and spouses named with the relationship stated, not in the tree, are added with that family, and the family is cited with the record type's family rating |
| G33 | Primary name with an empty Given and a given name in Surname: the name moves to Given; a married name on a record is added as an alternative name cited to it |
| G35 | People named with their relationship to someone in the tree stated, not already in the tree, are added when the evidence is reasonable: with their family, a Birth from the age (G22) and the record cited on their facts |

## 0. Working copy

`scripts/general/working_copy.py fetch`; after each apply, `push`.

## 1. Read (judgement)

For each citation: the people the saved reading (`notes/<type>_readings.md`) names, with their
relationship. Look each up: `scripts/records/person.py <tree> get --name "..."`,
`scripts/general/find_person.py <tree> --surname ... --given ...`, and the families of the people
already linked (`scripts/records/family.py <tree> get --person ID`). Sort them: in the tree already;
to add (G29, G35); not added (G28, transcription only).

## 2. Decisions (ask, all before step 3)

Standards apply without asking. Ask only, for example: a name that may be someone already in the
tree; a relationship the record states unclearly.

## 3. Fixes (dry run, apply; no confirmation)

| Fix | Command |
|---|---|
| Person (with primary name) | `scripts/records/person.py <tree> create --given G --surname S --sex male\|female\|unknown` |
| Alternative name (G33) | `scripts/records/name.py <tree> create --person P --given G --surname S`, then cite it (`citation_link.py create --owner name:N`) |
| Family, child | `scripts/records/family.py <tree> create --father P --mother P [--child P]`; `family.py <tree> edit F --add-child P` |
| Birth from the age (G22) | `scripts/records/event.py <tree> create --owner person:P --type 1 --date DR+...` |
| Cite the record on the new facts and family | `scripts/records/citation_link.py <tree> create --citation C --owner event:E --quality ~~~` |

Add `--apply` after checking each dry run. The person, event and family defaults come from the
one-off scripts (CLAUDE.md, scripts table): check new rows in RootsMagic.

## 4. Issues and finish

Open issues: a task linked to the person (`scripts/records/task.py`), a note on the citation, a row
in `notes/issues/<type>_issues.md`. Report the people added, then the issues one at a time.
