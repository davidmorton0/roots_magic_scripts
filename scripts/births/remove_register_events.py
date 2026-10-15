"""Remove birth register events, first copying their place to the Birth event.

For every birth register event of a person (default fact type 1024, "Birth
Register - UK"; --register-fact 1025 for "Birth Register Ireland"):
  - if the person's Birth event (fact type 1) has no place, give it the
    register event's place (the registration district);
  - delete the register event.
Not removed (listed instead): events named with --keep; events that still have
anything attached (citations, media, tasks, web links, witnesses, addresses);
events whose person has no Birth event, or more than one primary one.

Dry run by default: writes the proposed changes to
tmp/output/birth_register/<timestamp>_remove_register_events.txt and changes nothing.
--apply writes them in one transaction. RootsMagic must be closed, and the
file must be a working copy.

Usage: python remove_register_events.py PATH_TO_RMTREE [--keep EVENT_ID ...]
           [--register-fact ID] [--apply]
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
    problem: str = ""


def build_removals(
    conn: sqlite3.Connection, keep: set[int], register_fact: int = FACT_BIRTH_REGISTER
) -> list[Removal]:
    births = defaultdict(list)
    for eid, owner, primary, place in conn.execute(
        "SELECT EventID, OwnerID, IsPrimary, PlaceID FROM EventTable"
        " WHERE OwnerType = ? AND EventType = ?",
        (OWNER_PERSON, FACT_BIRTH),
    ):
        births[owner].append((eid, primary, place))
    attached = defaultdict(list)
    for kind, sql in ATTACHMENTS.items():
        for (eid,) in conn.execute(sql):
            attached[eid].append(kind)

    removals = []
    for eid, owner, date, place in conn.execute(
        "SELECT EventID, OwnerID, Date, PlaceID FROM EventTable"
        " WHERE OwnerType = ? AND EventType = ? ORDER BY EventID",
        (OWNER_PERSON, register_fact),
    ):
        r = Removal(eid, owner, date, place or 0)
        candidates = births.get(owner, [])
        primary = [b for b in candidates if b[1]]
        chosen = primary if primary else candidates
        if eid in keep:
            r.problem = "kept as requested"
        elif attached.get(eid):
            r.problem = f"still has {', '.join(sorted(set(attached[eid])))}"
        elif not candidates:
            r.problem = "person has no Birth event"
        elif len(chosen) > 1:
            r.problem = f"person has {len(chosen)} {'primary ' if primary else ''}Birth events"
        else:
            r.birth_id, _, birth_place = chosen[0]
            r.copy_place = not birth_place and bool(r.place_id)
        removals.append(r)
    return removals


def write_report(removals: list[Removal], names: dict[int, str], places: dict[int, str]) -> None:
    kept = [r for r in removals if r.problem]
    copies = [r for r in removals if r.copy_place and not r.problem]
    print(f"Register events: {len(removals)}; delete {len(removals) - len(kept)};"
          f" not deleted {len(kept)}; place copied to Birth event {len(copies)}")
    if kept:
        print("\n== Not deleted")
        for r in kept:
            print(f"   E{r.event_id} {names.get(r.person, '?')} [P{r.person}] {r.date}: {r.problem}")
    if copies:
        print("\n== Place copied to the Birth event (it has none)")
        for r in copies:
            print(f"   E{r.birth_id} {names.get(r.person, '?')} [P{r.person}]:"
                  f" {places.get(r.place_id, '?')} [L{r.place_id}]")
    print("\n== Events to delete")
    for r in removals:
        if not r.problem:
            print(f"   E{r.event_id} {names.get(r.person, '?')} [P{r.person}] {r.date},"
                  f" {places.get(r.place_id, '(no place)')}")


def apply(path, removals: list[Removal], register_fact: int = FACT_BIRTH_REGISTER) -> tuple[int, int]:
    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    deleted = copied = 0
    try:
        for r in removals:
            if r.problem:
                continue
            if r.copy_place:
                cur = conn.execute(
                    "UPDATE EventTable SET PlaceID = ?, UTCModDate = ?"
                    " WHERE EventID = ? AND PlaceID = 0",
                    (r.place_id, stamp, r.birth_id),
                )
                if cur.rowcount != 1:
                    raise RuntimeError(f"Birth event E{r.birth_id} not updated")
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
    return deleted, copied


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="remove_register_events.py PATH_TO_RMTREE")
    parser.add_argument("--keep", type=int, nargs="*", default=[], help="event IDs to keep")
    parser.add_argument("--register-fact", type=int, default=FACT_BIRTH_REGISTER,
                        help="fact type of the register events (default 1024, Birth Register - UK)")
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])

    conn = connect_readonly(path)
    try:
        removals = build_removals(conn, set(args.keep), args.register_fact)
        names = person_names(conn)
        places = dict(conn.execute("SELECT PlaceID, Name FROM PlaceTable"))
    finally:
        conn.close()

    kept = sum(1 for r in removals if r.problem)
    with output_file("remove_register_events", "birth_register"):
        write_report(removals, names, places)
    print(f"{len(removals)} register events; {len(removals) - kept} to delete; {kept} not deleted")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0
    deleted, copied = apply(path, removals, args.register_fact)
    print(f"Applied: {deleted} register events deleted; {copied} places copied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
