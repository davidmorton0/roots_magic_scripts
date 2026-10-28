"""Validate events, which RootsMagic shows as facts (EventTable), and their witnesses
(WitnessTable). Read-only.

Writes each event with an issue to tmp/output/validate/<timestamp>_validate_event.txt and prints a
summary of counts. after_death_facts (config) lists facts allowed after a death (e.g. Burial).

Usage: python validate_event.py PATH_TO_RMTREE [--config FILE]
"""

import re
import sys
from collections import Counter, defaultdict

from validate_common import (
    FACT_BIRTH,
    FACT_DEATH,
    FIRST_CUSTOM_FACT,
    OWNER_FAMILY,
    OWNER_PERSON,
    Checks,
    Tree,
    date_problem,
    run,
    sort_date_problem,
    year_of,
)

CHECKS = Checks()
YEAR_IN_NAME = re.compile(r"\b(1[5-9]\d\d|20\d\d)\b")
MIN_EVENTS_FOR_STYLE = 5


@CHECKS.add("record_event_no_citation", "Record events (custom facts) with no citation")
def record_event_no_citation(t: Tree) -> list[str]:
    return [t.event(row) for row in t.events if row[1] >= FIRST_CUSTOM_FACT and row[0] not in t.cited_events]


@CHECKS.add("event_no_citation", "Standard events (birth, death, marriage...) with no citation")
def event_no_citation(t: Tree) -> list[str]:
    return [t.event(row) for row in t.events if row[1] < FIRST_CUSTOM_FACT and row[0] not in t.cited_events]


@CHECKS.add("event_no_date", "Events with no date (where the fact type uses a date)")
def event_no_date(t: Tree) -> list[str]:
    return [t.event(row) for row in t.events if row[5] in (None, "", ".") and t.facts.get(row[1], ("", 1, 1))[1]]


@CHECKS.add("event_no_place", "Events with no place (where the fact type uses a place)")
def event_no_place(t: Tree) -> list[str]:
    return [t.event(row) for row in t.events if not row[4] and t.facts.get(row[1], ("", 1, 1))[2]]


@CHECKS.add("fact_year_mismatch", "Event year differs from the year in the fact name")
def fact_year_mismatch(t: Tree) -> list[str]:
    out = []
    for row in t.events:
        match = YEAR_IN_NAME.search(t.fact_name(row[1]))
        year = year_of(row[5])
        if match and year and year != int(match.group(1)):
            out.append(t.event(row))
    return out


@CHECKS.add("date_style_unusual", "Record events dated in a different style from most of their type")
def date_style_unusual(t: Tree) -> list[str]:
    def style(date):
        return date[:2] + date[12:13]

    by_fact = defaultdict(list)
    for row in t.events:
        if row[1] >= FIRST_CUSTOM_FACT and year_of(row[5]):
            by_fact[row[1]].append(row)
    out = []
    for fact, rows in sorted(by_fact.items()):
        if len(rows) < MIN_EVENTS_FOR_STYLE:
            continue
        counts = Counter(style(r[5]) for r in rows)
        common = counts.most_common(1)[0][0]
        example = next(r[5] for r in rows if style(r[5]) == common)
        for row in rows:
            if style(row[5]) != common:
                out.append(f"{t.event(row)} - most look like {example}")
    return out


@CHECKS.add("event_before_birth", "Person events dated before their birth year")
def event_before_birth(t: Tree) -> list[str]:
    out = []
    for row in t.person_events():
        born, year = t.births.get(row[3]), year_of(row[5])
        if row[1] != FACT_BIRTH and born and year and year < born:
            out.append(f"{t.event(row)} - born {born}")
    return out


@CHECKS.add("event_after_death", "Person events dated after their death year")
def event_after_death(t: Tree) -> list[str]:
    allowed = {name.lower() for name in t.cfg["after_death_facts"]}
    out = []
    for row in t.person_events():
        died, year = t.deaths.get(row[3]), year_of(row[5])
        name = t.fact_name(row[1]).lower()
        if row[1] != FACT_DEATH and name not in allowed and died and year and year > died:
            out.append(f"{t.event(row)} - died {died}")
    return out


@CHECKS.add("event_owner_missing", "Events whose person or family is missing")
def event_owner_missing(t: Tree) -> list[str]:
    exists = {OWNER_PERSON: t.names, OWNER_FAMILY: t.families}
    return [
        f"{t.fact_name(row[1])} [E{row[0]}] -> {'person' if row[2] == OWNER_PERSON else 'family'} {row[3]} missing"
        if row[2] in exists else f"{t.fact_name(row[1])} [E{row[0]}] -> owner type {row[2]} not known"
        for row in t.events
        if row[2] not in exists or row[3] not in exists[row[2]]
    ]


@CHECKS.add("event_date_form", "Event dates that are not a well-formed encoded date")
def event_date_form(t: Tree) -> list[str]:
    return [f"{t.event(row)}: {row[5]!r} {problem}" for row in t.events if (problem := date_problem(row[5]))]


@CHECKS.add("event_sort_date", "Event SortDate differs from the one worked out from the date")
def event_sort_date(t: Tree) -> list[str]:
    sorts = dict(t.conn.execute("SELECT EventID, SortDate FROM EventTable"))
    return [f"{t.event(row)}: {problem}" for row in t.events if (problem := sort_date_problem(row[5], sorts[row[0]]))]


@CHECKS.add("witness_orphan", "Witness entries whose event or person is missing")
def witness_orphan(t: Tree) -> list[str]:
    out = []
    for wid, eid, pid in t.conn.execute("SELECT WitnessID, EventID, PersonID FROM WitnessTable ORDER BY WitnessID"):
        if eid not in t.events_by_id:
            out.append(f"witness {wid}: event E{eid} missing")
        elif pid and pid not in t.names:
            out.append(f"witness {wid} on {t.event_id(eid)}: person P{pid} missing")
    return out


def main() -> int:
    return run(__doc__, "event", CHECKS)


if __name__ == "__main__":
    sys.exit(main())
