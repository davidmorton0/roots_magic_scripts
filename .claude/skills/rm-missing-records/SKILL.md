---
name: rm-missing-records
description: Make checklists of records still to find for the root person's family in the RootsMagic tree (birth, marriage and death register indexes, censuses, 1939 Register), one file per record type, starting with direct ancestors and widening by degrees of separation (0, 1, 2, ...). Read-only on the tree.
argument-hint: "<degree, e.g. 0, 1, 2> [path-to-rmtree]"
allowed-tools: Bash(mise exec -- python ${CLAUDE_PROJECT_DIR}/scripts/general/missing_records.py *)
---

Make the missing-record checklists. Read-only: never change the database.

Arguments: $ARGUMENTS
- First argument: the degree of separation to go out to (0, 1, 2, ...). If none is given, ask for it.
- Second argument: path to the .rmtree file. If none is given, use the working copy
  `tmp/work/Morton Tree.rmtree` when it exists and matches the test tree (`working_copy.py status`);
  otherwise fetch it first (`scripts/general/working_copy.py fetch`).

Run, from the project root:

```bash
mise exec -- python ${CLAUDE_PROJECT_DIR}/scripts/general/missing_records.py "<path>" --degree <N>
```

## Who is listed (user's rules, 2026-10-24)

- Degree 0: the root person (RootPerson in ConfigTable) and their direct ancestors.
- Degree n: brothers, sisters, spouses and children of the blood relatives of degree n-1.
- A spouse is listed but not followed further: their own parents, siblings and other spouses are
  not added. People related twice (e.g. cousins who married) are not treated specially yet.
- Order: degree 0 first, then each degree in the order people are reached.

## What counts as missing

- Only records from when the person was alive: from the Birth (or Christen) to the Death (or
  Burial); with neither, a maximum age of 100. Someone born less than 100 years ago with no Death
  or Burial is taken as living (no death item). When a missing death date is found and added, run
  the skill again: the lists shrink.
- A record is missing when no citation from that record type's sources touches the person (their
  events, names, the person, their families and family events). Sources are matched by name:
  `Birth Register - UK` (England and Wales; `- Scotland`, `- Ireland` likewise), `Marriage Register - UK`,
  `Death Register - UK`, `Census - England <year>` (or Wales, Scotland, Ireland, US), `Register - England 1939`.
- Countries: from the place of the person's dated event nearest to the date (default England).
  Registers: England and Wales from Jul 1837, Scotland from 1855, Ireland births and deaths from
  1864 and marriages from Apr 1845. Censuses: England, Wales, Scotland 1841-1921; Ireland 1901,
  1911; US 1850-1950 (not 1890); 1939 Register England and Wales.
- Marriages: one item per family of a blood relative, once; undated marriages show the first
  child's birth year. Deaths: a Death with no index citation, or "Death not in tree" with the years
  to search (last dated record to the Burial or age 100).
- People with no Birth or Christen date are listed at the end of each file, unchecked.

## Output

The script writes, in `notes/missing/` (git-ignored, real names):

| File | Record type |
|---|---|
| `missing_birth_registers.md` | Birth register (index) entries |
| `missing_censuses.md` | Censuses |
| `missing_1939_register.md` | 1939 Register |
| `missing_marriage_registers.md` | Marriage register (index) entries |
| `missing_death_registers.md` | Death register (index) entries |

Each file is rewritten on every run, so it always matches the tree: an item drops out once its
record is cited (records are added with the rm-add-record skill). Ticks or notes typed into the
files are lost on the next run.

Report the count per file and the number of people, in a short table. Do not list the items
unless asked.

## Adding a record type

Add it to `scripts/general/missing_records.py` (`FILES`, the source name prefixes and the dates
covered, and a block in `items_for`), add a case to `tests/test_missing_records.py`, and add the
file to the table above.
