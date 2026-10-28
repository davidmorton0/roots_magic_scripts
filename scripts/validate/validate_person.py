"""Validate people (PersonTable). Read-only.

PersonTable.ParentID should be 0 or a family the person is a child of (ChildTable), and SpouseID 0
or a family the person is a partner in (FamilyTable FatherID or MotherID); family.py keeps them so.

Writes each person with an issue to tmp/output/validate/<timestamp>_validate_person.txt and prints
a summary of counts. Names are checked by validate_name.py.

Usage: python validate_person.py PATH_TO_RMTREE [--config FILE]
"""

import sys
from collections import Counter

from validate_common import FACT_BIRTH, FACT_CHRISTEN, FACT_DEATH, Checks, Tree, run

CHECKS = Checks()


@CHECKS.add("person_no_name", "People with no primary name")
def person_no_name(t: Tree) -> list[str]:
    return [t.person(pid) for pid, name in sorted(t.names.items()) if name == "(no primary name)"]


@CHECKS.add("person_sex_code", "People whose sex code is not 0 or 1")
def person_sex_code(t: Tree) -> list[str]:
    return [f"{t.person(pid)} code {sex}" for pid, sex in sorted(t.sex.items()) if sex not in (0, 1)]


@CHECKS.add("person_no_events", "People with no events at all")
def person_no_events(t: Tree) -> list[str]:
    owners = {row[3] for row in t.person_events()}
    return [t.person(pid) for pid in sorted(t.names) if pid not in owners]


@CHECKS.add("person_no_birth", "People with no birth or christening event")
def person_no_birth(t: Tree) -> list[str]:
    owners = {row[3] for row in t.person_events() if row[1] in (FACT_BIRTH, FACT_CHRISTEN)}
    return [t.person(pid) for pid in sorted(t.names) if pid not in owners]


@CHECKS.add("person_unconnected", "People with no parents, partner or children")
def person_unconnected(t: Tree) -> list[str]:
    linked = {child for child, _ in t.children}
    linked |= {p for pair in t.families.values() for p in pair if p}
    return [t.person(pid) for pid in sorted(t.names) if pid not in linked]


@CHECKS.add("person_multiple_primary", "More than one primary birth or death event")
def person_multiple_primary(t: Tree) -> list[str]:
    counts = Counter((row[3], row[1]) for row in t.person_events() if row[1] in (FACT_BIRTH, FACT_DEATH) and row[6])
    return [
        f"{t.person(pid)} has {n} primary {t.fact_name(fact)} events"
        for (pid, fact), n in sorted(counts.items())
        if n > 1
    ]


@CHECKS.add("birth_after_death", "Birth year after death year")
def birth_after_death(t: Tree) -> list[str]:
    return [
        f"{t.person(pid)} born {born}, died {t.deaths[pid]}"
        for pid, born in sorted(t.births.items())
        if pid in t.deaths and born > t.deaths[pid]
    ]


@CHECKS.add("person_parent_family_bad", "ParentID is a missing family or one the person is not a child of")
def person_parent_family_bad(t: Tree) -> list[str]:
    child_of = {(child, fid) for child, fid in t.children}
    out = []
    for pid, parent in t.conn.execute("SELECT PersonID, ParentID FROM PersonTable WHERE ParentID <> 0 ORDER BY 1"):
        if parent not in t.families:
            out.append(f"{t.person(pid)} ParentID F{parent}: family missing")
        elif (pid, parent) not in child_of:
            out.append(f"{t.person(pid)} ParentID {t.family(parent)}: not a child of it")
    return out


@CHECKS.add("person_spouse_family_bad", "SpouseID is a missing family or one the person is not a partner in")
def person_spouse_family_bad(t: Tree) -> list[str]:
    out = []
    for pid, spouse in t.conn.execute("SELECT PersonID, SpouseID FROM PersonTable WHERE SpouseID <> 0 ORDER BY 1"):
        if spouse not in t.families:
            out.append(f"{t.person(pid)} SpouseID F{spouse}: family missing")
        elif pid not in t.families[spouse]:
            out.append(f"{t.person(pid)} SpouseID {t.family(spouse)}: not a partner in it")
    return out


def main() -> int:
    return run(__doc__, "person", CHECKS)


if __name__ == "__main__":
    sys.exit(main())
