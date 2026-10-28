"""Get, create, edit or delete places and place details (PlaceTable).

  get     ID [ID ...] | --name TEXT      Print places (read-only); --name matches part of the name.
  create  --name NAME [--master ID] [--set COLUMN=VALUE ...]
  edit    ID [--name NAME] [--set COLUMN=VALUE ...]
  delete  ID

A place (PlaceType 0) has a full name such as "Ilkeston, Derbyshire, England". A place detail
(PlaceType 2, made with --master PLACE_ID) has a short name and sits under a place. --set sets
Note or Abbrev. The sort name (Reverse) follows the name: for a place, the comma-separated parts in
reverse order, as RootsMagic writes it; for a detail, the name (on edit, only if Reverse held the
old name). New rows copy the scripts: Normalized empty, no coordinates, MasterID 0 for a place.

Refused when another place (or another detail under the same place) has the name, the master is not
a place, or (delete) the place is used by a fact (EventTable PlaceID or SiteID) or FAN row, or has
details under it.

Name is in an RMNOCASE index: run RootsMagic's rebuild indexes after create or edit.

create, edit and delete are dry runs by default: they print what would change. --apply writes it in
one transaction. RootsMagic must be closed, and the file must be a working copy.

Usage: python place.py PATH_TO_RMTREE get|create|edit|delete ... [--apply]
"""

import argparse
import sys
from pathlib import Path

from rmutils import (
    connect_readonly,
    db_path_arg,
    parse_assignments,
    reverse_name,
    stop_unless_applying,
    utc_mod_date,
    write_changes,
)

PLACE, DETAIL = 0, 2
SET_COLUMNS = ("Note", "Abbrev")


def uses(conn, pid: int) -> dict[str, int]:
    return {
        "facts": conn.execute("SELECT COUNT(*) FROM EventTable WHERE PlaceID = ?1 OR SiteID = ?1",
                              (pid,)).fetchone()[0],
        "FAN rows": conn.execute("SELECT COUNT(*) FROM FANTable WHERE PlaceID = ?1 OR SiteID = ?1",
                                 (pid,)).fetchone()[0],
        "place details": conn.execute("SELECT COUNT(*) FROM PlaceTable WHERE MasterID = ?", (pid,)).fetchone()[0],
    }


def clashes(conn, name: str, place_type: int, master: int, own_id: int = 0) -> list[int]:
    if place_type == DETAIL:
        rows = conn.execute("SELECT PlaceID FROM PlaceTable WHERE PlaceType = ? AND MasterID = ? AND Name = ?"
                            " AND PlaceID <> ?", (DETAIL, master, name, own_id))
    else:
        rows = conn.execute("SELECT PlaceID FROM PlaceTable WHERE PlaceType = ? AND Name = ? AND PlaceID <> ?",
                            (place_type, name, own_id))
    return [r[0] for r in rows]


def check_sets(sets: dict[str, str], problems: list[str]) -> None:
    for column in [c for c in sets if c not in SET_COLUMNS]:
        problems.append(f"--set {column!r} is not one of {', '.join(SET_COLUMNS)}")
        del sets[column]


def get(path: Path, args) -> int:
    conn = connect_readonly(path)
    try:
        ids = args.ids or [r[0] for r in conn.execute(
            "SELECT PlaceID FROM PlaceTable WHERE Name LIKE ? ORDER BY PlaceID", (f"%{args.name}%",))]
        if not ids:
            print("No places found")
            return 1
        for pid in ids:
            row = conn.execute("SELECT PlaceType, Name, Abbrev, Normalized, MasterID, Note, Reverse, Latitude,"
                               " Longitude, UTCModDate FROM PlaceTable WHERE PlaceID = ?", (pid,)).fetchone()
            if row is None:
                print(f"L{pid} not found")
                return 1
            kind, name, abbrev, normalized, master, note, reverse, lat, lon, stamp = row
            under = conn.execute("SELECT Name FROM PlaceTable WHERE PlaceID = ?", (master,)).fetchone()
            print(f"L{pid}  '{name}'  (PlaceType {kind}" + (f", under L{master} '{under[0]}'" if under else "") + ")")
            print(f"   Reverse: {reverse!r}")
            for label, value in (("Abbrev", abbrev), ("Normalized", normalized), ("Note", note)):
                if value:
                    print(f"   {label}: {value!r}")
            if lat or lon:
                print(f"   Latitude {lat}, Longitude {lon}")
            print("   uses: " + ", ".join(f"{k} {n}" for k, n in uses(conn, pid).items())
                  + f"  UTCModDate: {stamp}")
    finally:
        conn.close()
    return 0


def create(path: Path, args) -> int:
    problems = []
    sets = parse_assignments(args.set, "--set", problems)
    check_sets(sets, problems)
    place_type = DETAIL if args.master else PLACE
    conn = connect_readonly(path)
    try:
        if args.master and conn.execute("SELECT PlaceType FROM PlaceTable WHERE PlaceID = ?",
                                        (args.master,)).fetchone() != (PLACE,):
            problems.append(f"L{args.master} is not a place")
        found = clashes(conn, args.name, place_type, args.master)
        if found:
            problems.append(f"{args.name!r} already used by " + ", ".join(f"L{i}" for i in found))
    finally:
        conn.close()
    reverse = args.name if args.master else reverse_name(args.name)
    print(f"New {'detail under L' + str(args.master) if args.master else 'place'}: {args.name!r}"
          f" (PlaceType {place_type}); sort name {reverse!r}")
    for column, value in sets.items():
        print(f"   {column}: {value!r}")
    done = stop_unless_applying(problems, args.apply)
    if done is not None:
        return done

    def write(conn) -> int:
        return conn.execute(
            "INSERT INTO PlaceTable (PlaceType, Name, Abbrev, Normalized, Latitude, Longitude, LatLongExact, MasterID,"
            " Note, Reverse, fsID, anID, UTCModDate) VALUES (?, ?, ?, '', 0, 0, 0, ?, ?, ?, 0, 0, ?)",
            (place_type, args.name, sets.get("Abbrev", ""), args.master, sets.get("Note", ""), reverse,
             utc_mod_date())).lastrowid

    print(f"Applied: place L{write_changes(path, write)}. Run RootsMagic's rebuild indexes.")
    return 0


def edit(path: Path, args) -> int:
    problems = []
    changes = dict(parse_assignments(args.set, "--set", problems))
    check_sets(changes, problems)
    if args.name is not None:
        changes["Name"] = args.name
    if not changes:
        problems.append("nothing to change: give --name or --set")
    conn = connect_readonly(path)
    try:
        columns = list(changes) or ["Name"]
        row = conn.execute("SELECT PlaceType, MasterID, Name, Reverse, " + ", ".join(columns)
                           + " FROM PlaceTable WHERE PlaceID = ?", (args.id,)).fetchone()
        if row is None:
            print(f"L{args.id} not found")
            return 1
        place_type, master, old_name, reverse = row[:4]
        old = dict(zip(columns, row[4:]))
        if args.name is not None:
            found = clashes(conn, args.name, place_type, master, args.id)
            if found:
                problems.append(f"{args.name!r} already used by " + ", ".join(f"L{i}" for i in found))
    finally:
        conn.close()
    if args.name is not None:
        changes["Reverse"] = (args.name if reverse == old_name else reverse) if place_type == DETAIL \
            else reverse_name(args.name)
        old["Reverse"] = reverse
    print(f"L{args.id} '{old_name}':")
    for column, value in changes.items():
        print(f"   {column}: {old[column]!r} -> {value!r}")
    done = stop_unless_applying(problems, args.apply)
    if done is not None:
        return done

    def write(conn) -> None:
        assignments = {**changes, "UTCModDate": utc_mod_date()}
        conn.execute("UPDATE PlaceTable SET " + ", ".join(f"{c} = ?" for c in assignments) + " WHERE PlaceID = ?",
                     [*assignments.values(), args.id])

    write_changes(path, write)
    print(f"Applied: place L{args.id} changed. Run RootsMagic's rebuild indexes.")
    return 0


def delete(path: Path, args) -> int:
    conn = connect_readonly(path)
    try:
        row = conn.execute("SELECT Name FROM PlaceTable WHERE PlaceID = ?", (args.id,)).fetchone()
        used = uses(conn, args.id) if row else {}
    finally:
        conn.close()
    if row is None:
        print(f"L{args.id} not found")
        return 1
    print(f"Delete place L{args.id} {row[0]!r}")
    used = {k: n for k, n in used.items() if n}
    done = stop_unless_applying([f"still used: {used}"] if used else [], args.apply)
    if done is not None:
        return done
    write_changes(path, lambda conn: conn.execute("DELETE FROM PlaceTable WHERE PlaceID = ?", (args.id,)))
    print(f"Applied: place L{args.id} deleted.")
    return 0


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="place.py PATH_TO_RMTREE")
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("get")
    p.add_argument("ids", nargs="*", type=int)
    p.add_argument("--name")
    p.set_defaults(run=get)

    p = commands.add_parser("create")
    p.add_argument("--name", required=True)
    p.add_argument("--master", type=int, default=0)
    p.add_argument("--set", action="append", default=[])
    p.set_defaults(run=create)

    p = commands.add_parser("edit")
    p.add_argument("id", type=int)
    p.add_argument("--name")
    p.add_argument("--set", action="append", default=[])
    p.set_defaults(run=edit)

    p = commands.add_parser("delete")
    p.add_argument("id", type=int)
    p.set_defaults(run=delete)

    for name in ("create", "edit", "delete"):
        commands.choices[name].add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])
    if args.command == "get" and not args.ids and args.name is None:
        parser.error("get needs place IDs or --name")
    return args.run(path, args)


if __name__ == "__main__":
    sys.exit(main())
