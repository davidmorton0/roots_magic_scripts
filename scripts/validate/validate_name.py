"""Validate names (NameTable), primary and alternative. Read-only.

Name parts checked: Given, Surname, Prefix, Suffix, Nickname. "Case" reports a given name or surname
of more than one letter written all in lower case or all in capitals.

Writes each name with an issue to tmp/output/validate/<timestamp>_validate_name.txt and prints a
summary of counts. People with no primary name are reported by validate_person.py.

Usage: python validate_name.py PATH_TO_RMTREE [--config FILE]
"""

import sys
from collections import defaultdict

from validate_common import Checks, Tree, date_problem, full_name, run

CHECKS = Checks()
PARTS = ("Given", "Surname", "Prefix", "Suffix", "Nickname")


def names(t: Tree) -> list[tuple]:
    return t.conn.execute(
        "SELECT NameID, OwnerID, Given, Surname, Prefix, Suffix, Nickname, IsPrimary, Date FROM NameTable"
        " ORDER BY OwnerID, NameID").fetchall()


def label(t: Tree, row) -> str:
    nid, owner, given, surname = row[:4]
    kind = "primary" if row[7] else "alternative"
    return f"{full_name(given, surname)} ({kind}) [N{nid}] of {t.person(owner)}"


@CHECKS.add("name_owner_missing", "Names whose person is missing")
def name_owner_missing(t: Tree) -> list[str]:
    return [f"{full_name(r[2], r[3])} [N{r[0]}] -> P{r[1]} missing" for r in names(t) if r[1] not in t.names]


@CHECKS.add("name_part_blank", "Names with no given names or no surname")
def name_part_blank(t: Tree) -> list[str]:
    out = []
    for row in names(t):
        blank = [part for part, value in (("given names", row[2]), ("surname", row[3])) if not (value or "").strip()]
        if blank:
            out.append(f"{label(t, row)}: no {' and no '.join(blank)}")
    return out


@CHECKS.add("name_spaces", "Name parts with spaces at either end or two spaces together")
def name_spaces(t: Tree) -> list[str]:
    out = []
    for row in names(t):
        bad = [f"{part} {value!r}" for part, value in zip(PARTS, row[2:7])
               if value and (value != value.strip() or "  " in value)]
        if bad:
            out.append(f"{label(t, row)}: {', '.join(bad)}")
    return out


@CHECKS.add("name_case", "Given names or surnames all in lower case or all in capitals")
def name_case(t: Tree) -> list[str]:
    out = []
    for row in names(t):
        bad = [f"{part} {value!r}" for part, value in zip(PARTS[:2], row[2:4])
               if value and sum(c.isalpha() for c in value) > 1 and (value.islower() or value.isupper())]
        if bad:
            out.append(f"{label(t, row)}: {', '.join(bad)}")
    return out


@CHECKS.add("name_duplicate", "The same given names and surname twice for one person")
def name_duplicate(t: Tree) -> list[str]:
    groups = defaultdict(list)
    for row in names(t):
        groups[(row[1], (row[2] or "").casefold().strip(), (row[3] or "").casefold().strip())].append(row)
    return [
        f"{full_name(rows[0][2], rows[0][3])} of {t.person(rows[0][1])} [{', '.join(f'N{r[0]}' for r in rows)}]"
        for rows in groups.values()
        if len(rows) > 1
    ]


@CHECKS.add("name_date_form", "Name dates that are not a well-formed encoded date")
def name_date_form(t: Tree) -> list[str]:
    return [f"{label(t, row)} {row[8]!r}: {problem}" for row in names(t) if (problem := date_problem(row[8]))]


def main() -> int:
    return run(__doc__, "name", CHECKS)


if __name__ == "__main__":
    sys.exit(main())
