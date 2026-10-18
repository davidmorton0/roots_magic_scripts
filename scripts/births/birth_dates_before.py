"""Write quarter-only Birth (or Death) dates as "before" the end of the registration quarter.

For each Birth event (--fact 2: Death event) cited by the index source
(default 583, the birth index; e.g. 589 for the death index) whose date
says no more than the registration quarter in that citation (a range or
"between" over the quarter's first and last months, with or without "about"),
set it to "before" the month after the quarter: Jan-Mar 1886 -> before April
1886. Any other date is left alone: exact days, single months, years, and
quarters that differ from the citation's (those are listed).

Date codes, as RootsMagic 12 wrote and showed them (2026-10-15):
  DB+18860400..+00000000..   "Bef Apr 1886"
SortDate comes from rmutils.sort_date. Where the new date string already
exists elsewhere, its SortDate is used instead and any difference is reported.

Dry run by default: writes the proposed changes to
tmp/output/<folder>/<timestamp>_birth_dates_before.txt (--folder, default
birth_register) and changes nothing.
--apply writes them in one transaction. RootsMagic must be closed, and the
file must be a working copy.

Usage: python birth_dates_before.py PATH_TO_RMTREE [--source ID] [--fact ID]
           [--folder NAME] [--apply]
"""

import argparse
import re
import sys
from dataclasses import dataclass

from rmutils import (
    connect_readonly,
    connect_readwrite,
    db_path_arg,
    output_file,
    person_names,
    read_fields,
    sort_date,
    utc_mod_date,
)

DEFAULT_SOURCE = 583
OWNER_PERSON, OWNER_EVENT = 0, 2
FACT_BIRTH = 1
FACT_NAMES = {1: "Birth", 2: "Death"}
QUARTER_RANGES = ("D-", "DR")
CITING = re.compile(r"(?:Births|Deaths) registered in (?P<first>\w+), .* (?P<year>\d{4})$")
FIRST_MONTH = {"January": 1, "April": 4, "July": 7, "October": 10}
DATE_TABLES = ("EventTable", "MultimediaTable")


@dataclass
class Change:
    event_id: int
    person: int
    old_date: str
    new_date: str = ""
    new_sort: int = 0
    note: str = ""
    skip: str = ""


def before_date(year: int, first_month: int) -> tuple[str, int]:
    """'Before' the month after a quarter that starts in first_month, and its SortDate."""
    year, month = (year + 1, 1) if first_month == 10 else (year, first_month + 3)
    date = f"DB+{year}{month:02}00..+00000000.."
    return date, sort_date(date)


def quarter_of(citing: str) -> tuple[int, int] | None:
    match = CITING.search(citing or "")
    if not match or match.group("first") not in FIRST_MONTH:
        return None
    return int(match.group("year")), FIRST_MONTH[match.group("first")]


def is_quarter_only(date: str) -> tuple[int, int] | None:
    """(year, first month) if date is a range or between over a whole quarter."""
    if len(date) < 24 or date[:2] not in QUARTER_RANGES or date[13] != "+":
        return None
    first, last = date[3:11], date[14:22]
    if not (first.isdigit() and last.isdigit()) or first[6:] != "00" or last[6:] != "00":
        return None
    year, month = int(first[:4]), int(first[4:6])
    if month not in FIRST_MONTH.values() or last != f"{year}{month + 2:02}00":
        return None
    return year, month


def known_sort_dates(conn) -> dict[str, int]:
    known = {}
    for table in DATE_TABLES:
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if {"Date", "SortDate"} <= columns:
            for date, sort in conn.execute(f"SELECT Date, SortDate FROM {table} WHERE Date LIKE 'D%'"):
                known.setdefault(date, sort)
    return known


def build_changes(conn, source_id: int, fact: int = FACT_BIRTH) -> list[Change]:
    known = known_sort_dates(conn)
    quarters: dict[int, set] = {}
    events = {}
    for eid, owner, date, blob in conn.execute(
        """SELECT e.EventID, e.OwnerID, e.Date, c.Fields FROM EventTable e
           JOIN CitationLinkTable cl ON cl.OwnerType = ? AND cl.OwnerID = e.EventID
           JOIN CitationTable c ON c.CitationID = cl.CitationID
           WHERE c.SourceID = ? AND e.EventType = ? AND e.OwnerType = ?
           ORDER BY e.EventID""",
        (OWNER_EVENT, source_id, fact, OWNER_PERSON),
    ):
        events[eid] = (owner, date or "")
        quarter = quarter_of(read_fields(blob).get("Citing", ""))
        if quarter:
            quarters.setdefault(eid, set()).add(quarter)

    changes = []
    for eid, (owner, date) in events.items():
        event_quarter = is_quarter_only(date)
        if event_quarter is None:
            continue  # exact day, month, year, "before" already, etc.: left alone
        change = Change(eid, owner, date)
        cited = quarters.get(eid, set())
        if event_quarter not in cited:
            change.skip = "date's quarter differs from the citation's registration quarter"
        else:
            change.new_date, change.new_sort = before_date(*event_quarter)
            if change.new_date in known and known[change.new_date] != change.new_sort:
                change.note = (f"SortDate taken from an existing '{change.new_date}'"
                               f" ({known[change.new_date]}), not the computed {change.new_sort}")
                change.new_sort = known[change.new_date]
        changes.append(change)
    return changes


def write_report(changes: list[Change], names: dict[int, str], fact_name: str = "Birth") -> None:
    skipped = [c for c in changes if c.skip]
    noted = [c for c in changes if c.note]
    print(f"Quarter-only {fact_name} dates: {len(changes)}; change {len(changes) - len(skipped)};"
          f" left alone {len(skipped)}; SortDate differs from computed {len(noted)}")
    if skipped:
        print("\n== Left alone")
        for c in skipped:
            print(f"   E{c.event_id} {names.get(c.person, '?')} [P{c.person}] {c.old_date}: {c.skip}")
    if noted:
        print("\n== SortDate differs from the computed value")
        for c in noted:
            print(f"   E{c.event_id}: {c.note}")
    print("\n== Proposed changes")
    for c in changes:
        if not c.skip:
            print(f"   E{c.event_id} {names.get(c.person, '?')} [P{c.person}]:"
                  f" {c.old_date} -> {c.new_date} (SortDate {c.new_sort})")


def apply(path, changes: list[Change]) -> int:
    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    count = 0
    try:
        for c in changes:
            if c.skip:
                continue
            cur = conn.execute(
                "UPDATE EventTable SET Date = ?, SortDate = ?, UTCModDate = ?"
                " WHERE EventID = ? AND Date = ?",
                (c.new_date, c.new_sort, stamp, c.event_id, c.old_date),
            )
            if cur.rowcount != 1:
                raise RuntimeError(f"event E{c.event_id} not updated")
            count += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return count


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="birth_dates_before.py PATH_TO_RMTREE")
    parser.add_argument("--source", type=int, default=DEFAULT_SOURCE)
    parser.add_argument("--fact", type=int, default=FACT_BIRTH,
                        help="fact type whose dates change (default 1, Birth; 2 is Death)")
    parser.add_argument("--folder", default="birth_register", help="output folder")
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])
    fact_name = FACT_NAMES.get(args.fact, f"fact {args.fact}")

    conn = connect_readonly(path)
    try:
        changes = build_changes(conn, args.source, args.fact)
        names = person_names(conn)
    finally:
        conn.close()

    to_change = sum(1 for c in changes if not c.skip)
    with output_file("birth_dates_before", args.folder):
        write_report(changes, names, fact_name)
    print(f"{to_change} {fact_name} dates to change; {len(changes) - to_change} left alone")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0
    print(f"Applied: {apply(path, changes)} {fact_name} dates changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
