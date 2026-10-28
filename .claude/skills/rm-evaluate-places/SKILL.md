---
name: rm-evaluate-places
description: Evaluate the places of the facts a source's citations support (or every place) in the RootsMagic tree against G21 - flag addresses held in descriptions or as places, details not under their place, and the same address held twice - then move addresses to place details, rename, merge or delete places with dry runs and re-check.
argument-hint: "<source IDs>, or 'all'"
---

Evaluate places: $ARGUMENTS

Follow CLAUDE.md throughout. Item 7 of rm-record-cleanup step 5.

Flow as rm-evaluate-source: steps 0-3 read-only with every question asked up front (answers under
"Decisions" in `notes/issues/<type>_issues.md`); step 4 without further confirmation; issues at the end.

## Standard (from source_standards.md)

G21: a street or house address is a place detail (PlaceType 2) under the town, and the fact holds
both (PlaceID the town, SiteID the detail). The detail is named as the record writes it, house
number included. An existing detail with the same name under the same town is reused; a different
house number is a different detail; the same address held twice is merged (events moved to one,
the other deleted). A record giving only a town: the town, no detail. Addresses are never put in
the fact's description.

## 0. Working copy

`scripts/general/working_copy.py fetch`; after each apply, `push`.

## 1. Fetch and flag (script)

`scripts/places/evaluate_places.py "tmp/work/Morton Tree.rmtree" --source ID` (or `--all`). Read
`tmp/output/places/<timestamp>_evaluate_places.txt`. Codes: DESC (address in a description), PLACE
(address held as a place), MASTER (detail not under a place), SAME (same detail twice under one
place), SITE (event's detail not under its place). `scripts/validate/validate_place.py` adds unused
places and near-identical details.

## 2. Review (judgement)

The address patterns are a guess: a flagged name may be a parish ("St George Hanover Square") or a
farm. Check each against the record.

## 3. Decisions (ask, all before step 4)

Standards apply without asking (G21). Ask only, for example: which of two near-identical details
is kept, where the spellings differ on the records.

## 4. Fixes (dry run, apply; no confirmation)

| Fix | Command |
|---|---|
| New detail under the town | `scripts/records/place.py <tree> create --name "12 High Street" --master TOWN` |
| Event to town and detail | `scripts/records/event.py <tree> edit E --place TOWN --site DETAIL` |
| Address out of a description | `event.py <tree> edit E --set Details=` (after the detail is set) |
| Rename | `place.py <tree> edit L --name "..."` |
| Merge (SAME) | `scripts/places/merge_places.py` |
| Delete an unused place | `place.py <tree> delete L` |

Add `--apply` after checking each dry run. Place names are in RMNOCASE indexes: the user runs
RootsMagic's rebuild indexes when next opening the tree.

## 5. Re-check, issues and finish

Re-run step 1: each flag left is a recorded decision or an issue (`notes/issues/<type>_issues.md`;
a task where a person is affected). Report counts, then the issues one at a time.
