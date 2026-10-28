"""Fetch record events (facts 1000 and over) and say what each needs before it can be deleted (read-only).

G7: a record event is deleted once its date, place and citations are on the fact it stands for;
where the person has no such fact, the record event is changed into it. The record fact -> main
fact table is in .claude/skills/rm-remove-record-events/record_facts.md (--table FILE for another):

  DECIDE   no main fact agreed for this record fact yet (a row with "-")
  CONVERT  the owner has no matching main fact: change this event's type (records/event.py edit
           ID --type N); for a person's record of a family fact (Marriage), create it on the family
  COPY     the main fact lacks something the record event holds: its date, place or detail, a
           citation, a media link, its description or note
  READY    everything is on the main fact: delete it (records/event.py delete ID --with-links)
  NOROW    no row fits the record fact

Writes each record event to tmp/output/people/<timestamp>_evaluate_record_events.txt and prints
the counts per record fact and status.

Usage: python evaluate_record_events.py PATH_TO_RMTREE (--source ID ... | --fact ID ... | --event ID ... | --all)
           [--table FILE]
"""

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

from rmutils import PROJECT_DIR, connect_readonly, db_path_arg, load_rows, output_file, person_names

TABLE_FILE = PROJECT_DIR / ".claude" / "skills" / "rm-remove-record-events" / "record_facts.md"
OWNER_PERSON, OWNER_FAMILY, OWNER_EVENT = 0, 1, 2
FIRST_RECORD_FACT = 1000
COLUMNS = "EventID, EventType, OwnerType, OwnerID, PlaceID, SiteID, Date, IsPrimary, Details, Note"


def evaluate(conn, row, event, facts, fact_ids, names) -> tuple[str, list[str], str]:
    """(status, what to copy, description of the main fact)."""
    eid, etype, otype, oid, place, site, date, _, details, note = event
    if row is None:
        return "NOROW", [], ""
    main_name = row["Main fact"]
    if main_name == "-":
        return "DECIDE", [], ""
    main_type = fact_ids[main_name]
    family_fact = conn.execute("SELECT OwnerType FROM FactTypeTable WHERE FactTypeID = ?", (main_type,)).fetchone()[0]
    if family_fact == OWNER_FAMILY and otype == OWNER_PERSON:
        families = [f for (f,) in conn.execute("SELECT FamilyID FROM FamilyTable WHERE FatherID = ?1 OR MotherID = ?1",
                                               (oid,))]
        owners = [(OWNER_FAMILY, f) for f in families]
    else:
        owners = [(otype, oid)]
    candidates = [r for ot, o in owners for r in conn.execute(
        f"SELECT {COLUMNS} FROM EventTable WHERE EventType = ? AND OwnerType = ? AND OwnerID = ? ORDER BY"
        " IsPrimary DESC, EventID", (main_type, ot, o))]
    if row["Match"] == "date":
        candidates = [c for c in candidates if c[6] == date]
    if not candidates:
        if family_fact == OWNER_FAMILY and otype == OWNER_PERSON:
            where = ", ".join(f"F{f}" for _, f in owners) or "no family"
            return "CONVERT", [f"create {main_name} on the family ({where}), then copy"], ""
        dated = f" dated {date}" if row["Match"] == "date" else ""
        return "CONVERT", [f"no {main_name}{dated}: change this event's type to {main_type} ({main_name})"], ""
    main = candidates[0]
    mid, _, _, _, mplace, msite, mdate, _, mdetails, mnote = main
    copy = []
    if date not in (".", "") and mdate in (".", ""):
        copy.append(f"date {date}")
    if place and not mplace:
        copy.append(f"place L{place}")
    if site and not msite:
        copy.append(f"place detail L{site}")
    citations = {c for (c,) in conn.execute(
        "SELECT CitationID FROM CitationLinkTable WHERE OwnerType = ? AND OwnerID = ?", (OWNER_EVENT, eid))}
    on_main = {c for (c,) in conn.execute(
        "SELECT CitationID FROM CitationLinkTable WHERE OwnerType = ? AND OwnerID = ?", (OWNER_EVENT, mid))}
    copy += [f"citation C{c}" for c in sorted(citations - on_main)]
    media = conn.execute("SELECT COUNT(*) FROM MediaLinkTable WHERE OwnerType = ? AND OwnerID = ?",
                         (OWNER_EVENT, eid)).fetchone()[0]
    if media:
        copy.append(f"{media} media link(s)")
    for label, value in (("description", details), ("note", note)):
        if value and value.strip() and value.strip() not in f"{mdetails or ''} {mnote or ''}":
            copy.append(f"{label} {value.strip()[:60]!r}")
    described = f"E{mid} {main_name} {mdate}"
    return ("COPY" if copy else "READY"), copy, described


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="evaluate_record_events.py PATH_TO_RMTREE")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--source", type=int, action="append")
    which.add_argument("--fact", type=int, action="append")
    which.add_argument("--event", type=int, action="append")
    which.add_argument("--all", action="store_true")
    parser.add_argument("--table", type=Path, default=TABLE_FILE)
    args = parser.parse_args(sys.argv[2:])
    rows = load_rows(args.table, "Record facts", "Record fact")

    conn = connect_readonly(path)
    try:
        facts = dict(conn.execute("SELECT FactTypeID, Name FROM FactTypeTable"))
        fact_ids = {name: fid for fid, name in facts.items()}
        names = person_names(conn)
        sql = f"SELECT {COLUMNS} FROM EventTable WHERE EventType >= {FIRST_RECORD_FACT}"
        if args.all:
            events = conn.execute(sql + " ORDER BY EventType, EventID").fetchall()
        elif args.fact:
            events = [e for f in args.fact for e in conn.execute(sql + " AND EventType = ? ORDER BY EventID", (f,))]
        elif args.event:
            events = [e for i in args.event for e in conn.execute(sql + " AND EventID = ?", (i,))]
        else:
            events = [e for s in args.source for e in conn.execute(
                sql + " AND EventID IN (SELECT l.OwnerID FROM CitationLinkTable l JOIN CitationTable c USING"
                " (CitationID) WHERE l.OwnerType = 2 AND c.SourceID = ?) ORDER BY EventID", (s,))]
        if args.event and len(events) < len(args.event):
            found = {e[0] for e in events}
            print("Not record events or not found: " + ", ".join(f"E{i}" for i in args.event if i not in found))
            return 1
        results = []
        for event in events:
            fact = facts.get(event[1], f"fact {event[1]}")
            row = next((r for r in rows if any(p.fullmatch(fact) for p in r["_patterns"])), None)
            status, copy, main = evaluate(conn, row, event, facts, fact_ids, names)
            owner = f"P{event[3]} {names.get(event[3], '?')}" if event[2] == OWNER_PERSON else f"F{event[3]}"
            results.append((fact, status, event, owner, copy, main))
    finally:
        conn.close()

    with output_file("evaluate_record_events", "people"):
        print(f"File: {path}\nTable: {args.table}\n")
        for fact, status, event, owner, copy, main in results:
            print(f"E{event[0]} {fact} {event[6]} - {owner}: {status}" + (f" (main fact {main})" if main else ""))
            for item in copy:
                print(f"   - {item}")
    counts = defaultdict(Counter)
    for fact, status, *_ in results:
        counts[fact][status] += 1
    for fact, c in counts.items():
        print(f"{fact}: {sum(c.values())} events; " + ", ".join(f"{s} {n}" for s, n in sorted(c.items())))
    if not results:
        print("No record events")
    return 0


if __name__ == "__main__":
    sys.exit(main())
