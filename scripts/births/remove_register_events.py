"""Remove register events, first copying their place to the Birth (or Death) event.

For every register event of a person (default fact type 1024, "Birth
Register - UK"; --register-fact 1025 for "Birth Register Ireland", 1030 for
"Death Register"):
  - if the person's Birth event (fact type 1; --fact 2 for Death) has no
    place, give it the register event's place (the registration district);
  - delete the register event.
With --convert, a register event whose person has no Birth (Death) event is
changed into one instead, keeping its date, place, citations and other links,
and made the primary one.
Not removed (listed instead): events named with --keep; events that still have
anything attached (citations, media, tasks, web links, witnesses, addresses)
or have Details or a Note; events whose person has no Birth event (without
--convert), or more than one primary one.

Dry run by default: writes the proposed changes to
tmp/output/<folder>/<timestamp>_remove_register_events.txt (--folder, default
birth_register) and changes nothing.
--apply writes them in one transaction. RootsMagic must be closed, and the
file must be a working copy.

Usage: python remove_register_events.py PATH_TO_RMTREE [--keep EVENT_ID ...]
           [--register-fact ID] [--fact ID] [--convert] [--folder NAME] [--apply]
"""

import argparse
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass

from rmutils import (
    connect_readonly,
    connect_readwrite,
    db_path_arg,
    output_file,
    person_names,
    utc_mod_date,
)

OWNER_PERSON, OWNER_EVENT = 0, 2
FACT_BIRTH, FACT_BIRTH_REGISTER = 1, 1024
FACT_NAMES = {1: "Birth", 2: "Death"}
ATTACHMENTS = {
    "citations": "SELECT OwnerID FROM CitationLinkTable WHERE OwnerType = 2",
    "media": "SELECT OwnerID FROM MediaLinkTable WHERE OwnerType = 2",
    "tasks": "SELECT OwnerID FROM TaskLinkTable WHERE OwnerType = 2",
    "web links": "SELECT OwnerID FROM URLTable WHERE OwnerType = 2",
    "witnesses": "SELECT EventID FROM WitnessTable",
    "addresses": "SELECT OwnerID FROM AddressLinkTable WHERE OwnerType = 2",
}


@dataclass
class Removal:
    event_id: int
    person: int
    date: str
    place_id: int
    birth_id: int = 0
    copy_place: bool = False
    convert: bool = False
    problem: str = ""


def build_removals(
    conn: sqlite3.Connection, keep: set[int], register_fact: int = FACT_BIRTH_REGISTER,
    fact: int = FACT_BIRTH, convert: bool = False,
) -> list[Removal]:
    fact_name = FACT_NAMES.get(fact, f"fact {fact}")
    births = defaultdict(list)
    for eid, owner, primary, place in conn.execute(
        "SELECT EventID, OwnerID, IsPrimary, PlaceID FROM EventTable"
        " WHERE OwnerType = ? AND EventType = ?",
        (OWNER_PERSON, fact),
    ):
        births[owner].append((eid, primary, place))
    attached = defaultdict(list)
    for kind, sql in ATTACHMENTS.items():
        for (eid,) in conn.execute(sql):
            attached[eid].append(kind)

    removals = []
    for eid, owner, date, place, details, note in conn.execute(
        "SELECT EventID, OwnerID, Date, PlaceID, Details, Note FROM EventTable"
        " WHERE OwnerType = ? AND EventType = ? ORDER BY EventID",
        (OWNER_PERSON, register_fact),
    ):
        r = Removal(eid, owner, date, place or 0)
        candidates = births.get(owner, [])
        primary = [b for b in candidates if b[1]]
        chosen = primary if primary else candidates
        if eid in keep:
            r.problem = "kept as requested"
        elif not candidates and convert:
            r.convert = True
        elif attached.get(eid):
            r.problem = f"still has {', '.join(sorted(set(attached[eid])))}"
        elif details or note:
            r.problem = "has Details or a Note"
        elif not candidates:
            r.problem = f"person has no {fact_name} event"
        elif len(chosen) > 1:
            r.problem = f"person has {len(chosen)} {'primary ' if primary else ''}{fact_name} events"
        else:
            r.birth_id, _, birth_place = chosen[0]
            r.copy_place = not birth_place and bool(r.place_id)
        removals.append(r)
    return removals


def write_report(removals: list[Removal], names: dict[int, str], places: dict[int, str],
                 fact_name: str = "Birth") -> None:
    kept = [r for r in removals if r.problem]
    copies = [r for r in removals if r.copy_place and not r.problem]
    converts = [r for r in removals if r.convert]
    print(f"Register events: {len(removals)}; delete {len(removals) - len(kept) - len(converts)};"
          f" change into {fact_name} {len(converts)};"
          f" not deleted {len(kept)}; place copied to {fact_name} event {len(copies)}")
    if kept:
        print("\n== Not deleted")
        for r in kept:
            print(f"   E{r.event_id} {names.get(r.person, '?')} [P{r.person}] {r.date}: {r.problem}")
    if converts:
        print(f"\n== Changed into a {fact_name} event (the person has none)")
        for r in converts:
            print(f"   E{r.event_id} {names.get(r.person, '?')} [P{r.person}] {r.date},"
                  f" {places.get(r.place_id, '(no place)')}")
    if copies:
        print(f"\n== Place copied to the {fact_name} event (it has none)")
        for r in copies:
            print(f"   E{r.birth_id} {names.get(r.person, '?')} [P{r.person}]:"
                  f" {places.get(r.place_id, '?')} [L{r.place_id}]")
    print("\n== Events to delete")
    for r in removals:
        if not r.problem and not r.convert:
            print(f"   E{r.event_id} {names.get(r.person, '?')} [P{r.person}] {r.date},"
                  f" {places.get(r.place_id, '(no place)')}")


def apply(path, removals: list[Removal], register_fact: int = FACT_BIRTH_REGISTER,
          fact: int = FACT_BIRTH) -> tuple[int, int, int]:
    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    deleted = copied = converted = 0
    try:
        for r in removals:
            if r.problem:
                continue
            if r.convert:
                cur = conn.execute(
                    "UPDATE EventTable SET EventType = ?, IsPrimary = 1, UTCModDate = ?"
                    " WHERE EventID = ? AND EventType = ?",
                    (fact, stamp, r.event_id, register_fact),
                )
                if cur.rowcount != 1:
                    raise RuntimeError(f"register event E{r.event_id} not changed")
                converted += 1
                continue
            if r.copy_place:
                cur = conn.execute(
                    "UPDATE EventTable SET PlaceID = ?, UTCModDate = ?"
                    " WHERE EventID = ? AND PlaceID = 0",
                    (r.place_id, stamp, r.birth_id),
                )
                if cur.rowcount != 1:
                    raise RuntimeError(f"event E{r.birth_id} not updated")
                copied += 1
            cur = conn.execute(
                "DELETE FROM EventTable WHERE EventID = ? AND EventType = ?",
                (r.event_id, register_fact),
            )
            if cur.rowcount != 1:
                raise RuntimeError(f"register event E{r.event_id} not deleted")
            deleted += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return deleted, copied, converted


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="remove_register_events.py PATH_TO_RMTREE")
    parser.add_argument("--keep", type=int, nargs="*", default=[], help="event IDs to keep")
    parser.add_argument("--register-fact", type=int, default=FACT_BIRTH_REGISTER,
                        help="fact type of the register events (default 1024, Birth Register - UK)")
    parser.add_argument("--fact", type=int, default=FACT_BIRTH,
                        help="fact type that keeps the place (default 1, Birth; 2 is Death)")
    parser.add_argument("--convert", action="store_true",
                        help="change a register event into that fact where the person has none")
    parser.add_argument("--folder", default="birth_register", help="output folder")
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])
    fact_name = FACT_NAMES.get(args.fact, f"fact {args.fact}")

    conn = connect_readonly(path)
    try:
        removals = build_removals(conn, set(args.keep), args.register_fact, args.fact, args.convert)
        names = person_names(conn)
        places = dict(conn.execute("SELECT PlaceID, Name FROM PlaceTable"))
    finally:
        conn.close()

    kept = sum(1 for r in removals if r.problem)
    converts = sum(1 for r in removals if r.convert)
    with output_file("remove_register_events", args.folder):
        write_report(removals, names, places, fact_name)
    print(f"{len(removals)} register events; {len(removals) - kept - converts} to delete;"
          f" {converts} to change into {fact_name}; {kept} not deleted")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0
    deleted, copied, converted = apply(path, removals, args.register_fact, args.fact)
    print(f"Applied: {deleted} register events deleted; {copied} places copied;"
          f" {converted} changed into {fact_name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
