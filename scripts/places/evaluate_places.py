"""Fetch places and the events using them and flag what does not fit G21 (read-only).

G21: a street or house address is a place detail (PlaceType 2) under the town, and the fact holds
both (PlaceID the town, SiteID the detail); named as the record writes it; the same address held
twice is merged; an address is never put in the fact's description.

  DESC     an event's description (Details) looks like an address
  PLACE    a place (PlaceType 0) whose first part is a house number or a street: an address held
           as a place instead of a detail under the town
  MASTER   a place detail whose place is missing or is not a place (PlaceType 0)
  SAME     place details under one place with the same name apart from case, spaces and
           punctuation (merge: scripts/places/merge_places.py)
  SITE     an event whose place detail is not under its place, or has a detail but no place

With --source, only the events linked to that source's citations and their places are checked.
Writes each flag to tmp/output/places/<timestamp>_evaluate_places.txt and prints counts.

Usage: python evaluate_places.py PATH_TO_RMTREE (--source ID ... | --all)
"""

import argparse
import re
import sys
from collections import Counter, defaultdict

from rmutils import connect_readonly, db_path_arg, output_file

PLACE, DETAIL = 0, 2
STREETS = ("Street|St|Road|Rd|Lane|Terrace|Place|Row|Square|Avenue|Ave|Court|Yard|Walk|Gardens|Grove|Crescent|Close"
           "|Drive|Buildings|Cottages")
HOUSE = re.compile(r"\d+[a-zA-Z]?\b")
STREET = re.compile(rf"\b({STREETS})\.?$")
ADDRESS = re.compile(rf"\b\d+[a-zA-Z]?,? [A-Z][\w']*( [A-Z][\w']*)* ({STREETS})\b")


def key(name: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", "", name or "").casefold().split())


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="evaluate_places.py PATH_TO_RMTREE")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--source", type=int, action="append")
    which.add_argument("--all", action="store_true")
    args = parser.parse_args(sys.argv[2:])

    conn = connect_readonly(path)
    try:
        places = {pid: (ptype, name, master) for pid, ptype, name, master in conn.execute(
            "SELECT PlaceID, PlaceType, Name, MasterID FROM PlaceTable")}
        sql = "SELECT EventID, EventType, PlaceID, SiteID, Details FROM EventTable"
        if args.all:
            events = conn.execute(sql + " ORDER BY EventID").fetchall()
        else:
            events = [e for s in args.source for e in conn.execute(
                sql + " WHERE EventID IN (SELECT l.OwnerID FROM CitationLinkTable l JOIN CitationTable c USING"
                " (CitationID) WHERE l.OwnerType = 2 AND c.SourceID = ?) ORDER BY EventID", (s,))]
        facts = dict(conn.execute("SELECT FactTypeID, Name FROM FactTypeTable"))
    finally:
        conn.close()

    in_scope = set(places) if args.all else {p for e in events for p in e[2:4] if p}
    in_scope |= {places[p][2] for p in list(in_scope) if p in places and places[p][0] == DETAIL}
    flags = []
    for eid, etype, place, site, details in events:
        label = f"E{eid} {facts.get(etype, etype)}"
        if details and ADDRESS.search(details):
            flags.append(f"DESC {label}: description {details!r} looks like an address")
        if site and not place:
            flags.append(f"SITE {label}: place detail L{site} but no place")
        elif site and site in places and places[site][2] != place:
            flags.append(f"SITE {label}: place detail L{site} '{places[site][1]}' is under L{places[site][2]},"
                         f" not the event's place L{place}")
    details_by_master = defaultdict(list)
    for pid in sorted(in_scope):
        if pid not in places:
            continue
        ptype, name, master = places[pid]
        first = (name or "").split(",")[0].strip()
        if ptype == PLACE and (HOUSE.match(first) or STREET.search(first)):
            flags.append(f"PLACE L{pid} '{name}': the first part looks like an address (a detail under the town)")
        if ptype == DETAIL:
            if master not in places or places[master][0] != PLACE:
                flags.append(f"MASTER L{pid} '{name}': its place L{master} is missing or not a place")
            details_by_master[master].append((pid, name))
    for master, details in sorted(details_by_master.items()):
        groups = defaultdict(list)
        for pid, name in details:
            groups[key(name)].append((pid, name))
        for same in groups.values():
            if len(same) > 1:
                flags.append(f"SAME under L{master} '{places.get(master, (0, '?'))[1]}': "
                             + ", ".join(f"L{p} '{n}'" for p, n in same))

    with output_file("evaluate_places", "places"):
        print(f"File: {path}\n")
        for flag in flags:
            print(f"! {flag}")
    counts = Counter(flag.split()[0] for flag in flags)
    print(f"{len(events)} events, {len(in_scope)} places checked; {len(flags)} flags"
          + ("; " + ", ".join(f"{c} {n}" for c, n in sorted(counts.items())) if counts else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
