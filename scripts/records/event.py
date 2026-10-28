"""Get, create, edit or delete events, which RootsMagic shows as facts (EventTable).

  get     ID [ID ...] | --owner KIND:ID [--type N]     Print events (read-only).
  create  --owner KIND:ID --type N [--date RM_DATE] [--place ID] [--site ID] [--primary 0|1]
          [--set COLUMN=VALUE ...]
  edit    ID [--type N] [--date RM_DATE] [--place ID] [--site ID] [--primary 0|1] [--set COLUMN=VALUE ...]
  delete  ID [--with-links]

KIND is person or family (OwnerType 0, 1; the ID is a PersonID or FamilyID). --type is a
FactTypeTable ID (1 Birth, 2 Death, 3 Christen, 300 Marriage, 1000+ custom); it must belong to the
owner kind. --date is RootsMagic's encoded text ("." for none, the default); SortDate comes from
rmutils, so a date form it does not know is refused. --place is a place (PlaceType 0), --site a
detail (PlaceType 2) under that place; 0 clears. --set sets Sentence, Details or Note. A new event
is primary (IsPrimary 1) when the owner has no event of that type, else 0, unless --primary is given.
New rows copy the one-off scripts (not yet checked against an event made by hand): FamilyID 0,
IsPrivate, Proof and Status 0.

Refused when the owner, event, fact type, place or detail does not exist, the detail is not under
the place, or (delete) the event has media or witnesses, or has citation links and --with-links is
not given. Delete removes the event and its citation links, not the citations.

create, edit and delete are dry runs by default: they print what would change. --apply writes it in
one transaction. RootsMagic must be closed, and the file must be a working copy.

Usage: python event.py PATH_TO_RMTREE get|create|edit|delete ... [--apply]
"""

import argparse
import sys
from pathlib import Path

from rmutils import (
    NO_DATE,
    connect_readonly,
    db_path_arg,
    event_sort_date,
    parse_assignments,
    stop_unless_applying,
    utc_mod_date,
    write_changes,
)

OWNERS = {"person": (0, "PersonTable", "PersonID"), "family": (1, "FamilyTable", "FamilyID")}
OWNER_EVENT = 2
PLACE, DETAIL = 0, 2
SET_COLUMNS = ("Sentence", "Details", "Note")


def parse_owner(text: str, problems: list[str]) -> tuple[str, int] | None:
    kind, _, owner = text.partition(":")
    if kind not in OWNERS or not owner.isdigit():
        problems.append(f"--owner {text!r} is not KIND:ID (kind {', '.join(OWNERS)})")
        return None
    return kind, int(owner)


def place_name(conn, pid) -> str:
    row = conn.execute("SELECT Name FROM PlaceTable WHERE PlaceID = ?", (pid,)).fetchone()
    return f"L{pid} {row[0]}" if row else "-"


def check_place(conn, place: int, site: int, problems: list[str]) -> None:
    if place and (conn.execute("SELECT PlaceType FROM PlaceTable WHERE PlaceID = ?", (place,)).fetchone()
                  != (PLACE,)):
        problems.append(f"L{place} is not a place")
    if site and conn.execute("SELECT PlaceType, MasterID FROM PlaceTable WHERE PlaceID = ?",
                             (site,)).fetchone() != (DETAIL, place):
        problems.append(f"L{site} is not a detail under L{place}")


def check_type(conn, fact: int, owner_code: int, problems: list[str]) -> None:
    row = conn.execute("SELECT OwnerType FROM FactTypeTable WHERE FactTypeID = ?", (fact,)).fetchone()
    if row is None:
        problems.append(f"fact type {fact} not found")
    elif row[0] != owner_code:
        problems.append(f"fact type {fact} is not a {'person' if owner_code == 0 else 'family'} fact")


def check_sets(sets: dict[str, str], problems: list[str]) -> None:
    for column in [c for c in sets if c not in SET_COLUMNS]:
        problems.append(f"--set {column!r} is not one of {', '.join(SET_COLUMNS)}")
        del sets[column]


def fact_name(conn, fact: int) -> str:
    row = conn.execute("SELECT Name FROM FactTypeTable WHERE FactTypeID = ?", (fact,)).fetchone()
    return row[0] if row else f"fact {fact}"


def get(path: Path, args) -> int:
    problems = []
    owner = parse_owner(args.owner, problems) if args.owner else None
    if problems:
        print(problems[0])
        return 1
    conn = connect_readonly(path)
    try:
        if args.ids:
            ids = args.ids
        else:
            sql = "SELECT EventID FROM EventTable WHERE OwnerType = ? AND OwnerID = ?"
            params = [OWNERS[owner[0]][0], owner[1]]
            if args.type is not None:
                sql += " AND EventType = ?"
                params.append(args.type)
            ids = [r[0] for r in conn.execute(sql + " ORDER BY SortDate, EventID", params)]
        if not ids:
            print("No events found")
            return 1
        for eid in ids:
            row = conn.execute("SELECT EventType, OwnerType, OwnerID, PlaceID, SiteID, Date, SortDate, IsPrimary,"
                               " Sentence, Details, Note, UTCModDate FROM EventTable WHERE EventID = ?",
                               (eid,)).fetchone()
            if row is None:
                print(f"E{eid} not found")
                return 1
            fact, owner_type, owner_id, place, site, date_, sort, primary, sentence, details, note, stamp = row
            kind = "person" if owner_type == 0 else "family" if owner_type == 1 else f"type {owner_type}"
            print(f"E{eid}  {fact_name(conn, fact)} (fact {fact})  {kind} {owner_id}  Date {date_}  SortDate {sort}"
                  f"  IsPrimary {primary}")
            print(f"   place: {place_name(conn, place)} / {place_name(conn, site)}")
            for label, value in (("Sentence", sentence), ("Details", details), ("Note", note)):
                if value:
                    print(f"   {label}: {value!r}")
            counts = {
                "citations": conn.execute("SELECT COUNT(*) FROM CitationLinkTable WHERE OwnerType = ? AND OwnerID = ?",
                                          (OWNER_EVENT, eid)).fetchone()[0],
                "media": conn.execute("SELECT COUNT(*) FROM MediaLinkTable WHERE OwnerType = ? AND OwnerID = ?",
                                      (OWNER_EVENT, eid)).fetchone()[0],
                "witnesses": conn.execute("SELECT COUNT(*) FROM WitnessTable WHERE EventID = ?", (eid,)).fetchone()[0],
            }
            print("   uses: " + ", ".join(f"{k} {n}" for k, n in counts.items()) + f"  UTCModDate: {stamp}")
    finally:
        conn.close()
    return 0


def create(path: Path, args) -> int:
    problems = []
    owner = parse_owner(args.owner, problems)
    sets = parse_assignments(args.set, "--set", problems)
    check_sets(sets, problems)
    sort = event_sort_date(args.date)
    if sort is None:
        problems.append(f"--date {args.date!r}: SortDate not known for this form of date")
    conn = connect_readonly(path)
    try:
        primary = args.primary
        if owner:
            code, table, key = OWNERS[owner[0]]
            if not conn.execute(f"SELECT 1 FROM {table} WHERE {key} = ?", (owner[1],)).fetchone():
                problems.append(f"{owner[0]} {owner[1]} not found")
            check_type(conn, args.type, code, problems)
            if primary is None:
                primary = 0 if conn.execute("SELECT 1 FROM EventTable WHERE OwnerType = ? AND OwnerID = ?"
                                            " AND EventType = ?", (code, owner[1], args.type)).fetchone() else 1
        check_place(conn, args.place, args.site, problems)
    finally:
        conn.close()
    print(f"New event: fact {args.type} for {args.owner}, date {args.date} (SortDate {sort}), place L{args.place}"
          f" / L{args.site}, IsPrimary {primary}")
    for column, value in sets.items():
        print(f"   {column}: {value!r}")
    done = stop_unless_applying(problems, args.apply)
    if done is not None:
        return done

    def write(conn) -> int:
        return conn.execute(
            "INSERT INTO EventTable (EventType, OwnerType, OwnerID, FamilyID, PlaceID, SiteID, Date, SortDate,"
            " IsPrimary, IsPrivate, Proof, Status, Sentence, Details, Note, UTCModDate)"
            " VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?, ?, ?)",
            (args.type, OWNERS[owner[0]][0], owner[1], args.place, args.site, args.date, sort, primary,
             sets.get("Sentence", ""), sets.get("Details", ""), sets.get("Note", ""), utc_mod_date())).lastrowid

    print(f"Applied: event E{write_changes(path, write)}.")
    return 0


def edit(path: Path, args) -> int:
    problems = []
    changes = dict(parse_assignments(args.set, "--set", problems))
    check_sets(changes, problems)
    if args.type is not None:
        changes["EventType"] = args.type
    if args.date is not None:
        sort = event_sort_date(args.date)
        if sort is None:
            problems.append(f"--date {args.date!r}: SortDate not known for this form of date")
        changes.update(Date=args.date, SortDate=sort)
    if args.place is not None:
        changes["PlaceID"] = args.place
    if args.site is not None:
        changes["SiteID"] = args.site
    if args.primary is not None:
        changes["IsPrimary"] = args.primary
    if not changes:
        problems.append("nothing to change")
    conn = connect_readonly(path)
    try:
        columns = list(changes) or ["Date"]
        row = conn.execute("SELECT OwnerType, PlaceID, SiteID, " + ", ".join(columns)
                           + " FROM EventTable WHERE EventID = ?", (args.id,)).fetchone()
        if row is None:
            print(f"E{args.id} not found")
            return 1
        owner_type, old_place, old_site = row[:3]
        old = dict(zip(columns, row[3:]))
        if args.type is not None:
            check_type(conn, args.type, owner_type, problems)
        if args.place is not None or args.site is not None:
            check_place(conn, changes.get("PlaceID", old_place), changes.get("SiteID", old_site), problems)
    finally:
        conn.close()
    print(f"E{args.id}:")
    for column, value in changes.items():
        print(f"   {column}: {old.get(column)!r} -> {value!r}")
    done = stop_unless_applying(problems, args.apply)
    if done is not None:
        return done

    def write(conn) -> None:
        assignments = {**changes, "UTCModDate": utc_mod_date()}
        conn.execute("UPDATE EventTable SET " + ", ".join(f"{c} = ?" for c in assignments) + " WHERE EventID = ?",
                     [*assignments.values(), args.id])

    write_changes(path, write)
    print(f"Applied: event E{args.id} changed.")
    return 0


def delete(path: Path, args) -> int:
    conn = connect_readonly(path)
    try:
        row = conn.execute("SELECT EventType, OwnerType, OwnerID, Date FROM EventTable WHERE EventID = ?",
                           (args.id,)).fetchone()
        if row is None:
            print(f"E{args.id} not found")
            return 1
        links = conn.execute("SELECT COUNT(*) FROM CitationLinkTable WHERE OwnerType = ? AND OwnerID = ?",
                             (OWNER_EVENT, args.id)).fetchone()[0]
        media = conn.execute("SELECT COUNT(*) FROM MediaLinkTable WHERE OwnerType = ? AND OwnerID = ?",
                             (OWNER_EVENT, args.id)).fetchone()[0]
        witnesses = conn.execute("SELECT COUNT(*) FROM WitnessTable WHERE EventID = ?", (args.id,)).fetchone()[0]
        name = fact_name(conn, row[0])
    finally:
        conn.close()
    print(f"Delete event E{args.id} {name}, owner type {row[1]} ID {row[2]}, {row[3]}:"
          f" {links} citation links, {media} media, {witnesses} witnesses")
    problems = []
    if media:
        problems.append(f"{media} media are attached; remove their media links first")
    if witnesses:
        problems.append(f"{witnesses} witness entries; remove them first")
    if links and not args.with_links:
        problems.append(f"{links} citation links; give --with-links to delete them too")
    done = stop_unless_applying(problems, args.apply)
    if done is not None:
        return done

    def write(conn) -> None:
        conn.execute("DELETE FROM CitationLinkTable WHERE OwnerType = ? AND OwnerID = ?", (OWNER_EVENT, args.id))
        conn.execute("DELETE FROM EventTable WHERE EventID = ?", (args.id,))

    write_changes(path, write)
    print(f"Applied: event E{args.id} deleted.")
    return 0


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="event.py PATH_TO_RMTREE")
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("get")
    p.add_argument("ids", nargs="*", type=int)
    p.add_argument("--owner")
    p.add_argument("--type", type=int)
    p.set_defaults(run=get)

    p = commands.add_parser("create")
    p.add_argument("--owner", required=True)
    p.add_argument("--type", type=int, required=True)
    p.add_argument("--date", default=NO_DATE)
    p.add_argument("--place", type=int, default=0)
    p.add_argument("--site", type=int, default=0)
    p.set_defaults(run=create)

    p = commands.add_parser("edit")
    p.add_argument("id", type=int)
    p.add_argument("--type", type=int)
    p.add_argument("--date")
    p.add_argument("--place", type=int)
    p.add_argument("--site", type=int)
    p.set_defaults(run=edit)

    p = commands.add_parser("delete")
    p.add_argument("id", type=int)
    p.add_argument("--with-links", action="store_true")
    p.set_defaults(run=delete)

    for name in ("create", "edit"):
        sub = commands.choices[name]
        sub.add_argument("--primary", type=int, choices=(0, 1))
        sub.add_argument("--set", action="append", default=[])
    for name in ("create", "edit", "delete"):
        commands.choices[name].add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])
    if args.command == "get" and not args.ids and not args.owner:
        parser.error("get needs event IDs or --owner")
    return args.run(path, args)


if __name__ == "__main__":
    sys.exit(main())
