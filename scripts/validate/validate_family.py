"""Validate families (FamilyTable) and their children (ChildTable). Read-only.

Age limits come from the config (min_parent_age, max_mother_age, min_marriage_age).

Writes each family with an issue to tmp/output/validate/<timestamp>_validate_family.txt and prints
a summary of counts.

Usage: python validate_family.py PATH_TO_RMTREE [--config FILE]
"""

import sys
from collections import Counter

from validate_common import OWNER_FAMILY, Checks, Tree, run, year_of

CHECKS = Checks()


@CHECKS.add("family_one_partner", "Families with only one partner recorded")
def family_one_partner(t: Tree) -> list[str]:
    return [t.family(fid) for fid, (father, mother) in sorted(t.families.items()) if not father or not mother]


@CHECKS.add("parent_age", "Parent too young, too old, or dead at a child's birth")
def parent_age(t: Tree) -> list[str]:
    min_age, max_mother = t.cfg["min_parent_age"], t.cfg["max_mother_age"]
    out = []
    for child, fid in t.children:
        born = t.births.get(child)
        if not born:
            continue
        father, mother = t.families.get(fid, (0, 0))
        for parent, role in ((father, "father"), (mother, "mother")):
            problems = []
            parent_born, parent_died = t.births.get(parent), t.deaths.get(parent)
            if parent_born:
                age = born - parent_born
                if age < min_age:
                    problems.append(f"{role} aged {age}")
                if role == "mother" and age > max_mother:
                    problems.append(f"mother aged {age}")
            if parent_died:
                limit = parent_died + (1 if role == "father" else 0)
                if born > limit:
                    problems.append(f"{role} died {parent_died}")
            if parent and problems:
                out.append(f"{t.person(child)} born {born} - {t.person(parent)}: {', '.join(problems)}")
    return out


@CHECKS.add("family_event_age", "Family events (e.g. marriage) with a partner under age or dead")
def family_event_age(t: Tree) -> list[str]:
    min_age = t.cfg["min_marriage_age"]
    out = []
    for row in t.events:
        year = year_of(row[5])
        if row[2] != OWNER_FAMILY or not year:
            continue
        problems = []
        for partner in t.families.get(row[3], (0, 0)):
            born, died = t.births.get(partner), t.deaths.get(partner)
            if born and year - born < min_age:
                problems.append(f"{t.person(partner)} aged {year - born}")
            if died and year > died:
                problems.append(f"{t.person(partner)} died {died}")
        if problems:
            out.append(f"{t.event(row)} - {', '.join(problems)}")
    return out


@CHECKS.add("family_partner_missing", "Families whose father or mother is a missing person")
def family_partner_missing(t: Tree) -> list[str]:
    return [
        f"F{fid}: {role} P{pid} missing"
        for fid, pair in sorted(t.families.items())
        for role, pid in zip(("father", "mother"), pair)
        if pid and pid not in t.names
    ]


@CHECKS.add("child_orphan", "Child rows whose person or family is missing, or listed twice")
def child_orphan(t: Tree) -> list[str]:
    out = []
    for child, fid in t.children:
        if fid not in t.families:
            out.append(f"{t.person(child)} child of F{fid}: family missing")
        elif child not in t.names:
            out.append(f"child P{child} of {t.family(fid)}: person missing")
    counts = Counter(t.children)
    out += [f"{t.person(child)} listed {n} times as a child of {t.family(fid)}"
            for (child, fid), n in sorted(counts.items()) if n > 1]
    return out


def main() -> int:
    return run(__doc__, "family", CHECKS)


if __name__ == "__main__":
    sys.exit(main())
