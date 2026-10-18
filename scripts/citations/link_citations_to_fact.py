"""Link a source's citations to another fact of the same person.

For every citation of --source whose SpecificItem field matches --item
(re.search), find the person it is linked to (through an event or directly)
and add a citation link to that person's --fact event (e.g. 1 Birth), with
--quality. The new link copies RootsMagic's own rows: SortOrder 0, IsPrivate
0, Flags 0.

Not linked (listed instead): the citation is linked to no person or to more
than one; the person has no such event, or more than one primary one; the
event already has the citation.

Dry run by default: writes the proposed links to
tmp/output/<folder>/<timestamp>_link_citations_to_fact.txt and changes nothing.
--apply writes them in one transaction. RootsMagic must be closed, and the
file must be a working copy.

Usage: python link_citations_to_fact.py PATH_TO_RMTREE --source ID --fact ID
           --item REGEX --quality XYZ [--folder NAME] [--apply]
"""

import argparse
import re
import sys
from collections import defaultdict

from rmutils import (
    connect_readonly,
    connect_readwrite,
    db_path_arg,
    output_file,
    person_names,
    read_fields,
    utc_mod_date,
)

OWNER_PERSON, OWNER_EVENT = 0, 2
QUALITY = re.compile(r"^[PS~][DIN~][OX~]$")


def build_links(conn, source: int, fact: int, item: str) -> tuple[list, list]:
    """([(citation, person, event)], [(citation, person, problem)])."""
    events = defaultdict(list)
    for eid, owner, primary in conn.execute(
        "SELECT EventID, OwnerID, IsPrimary FROM EventTable WHERE OwnerType = ? AND EventType = ?",
        (OWNER_PERSON, fact),
    ):
        events[owner].append((eid, primary))
    people, linked = defaultdict(set), defaultdict(set)
    for cid, otype, oid, e_otype, e_owner in conn.execute(
        """SELECT cl.CitationID, cl.OwnerType, cl.OwnerID, e.OwnerType, e.OwnerID
           FROM CitationLinkTable cl JOIN CitationTable c USING (CitationID)
           LEFT JOIN EventTable e ON cl.OwnerType = ? AND e.EventID = cl.OwnerID
           WHERE c.SourceID = ?""",
        (OWNER_EVENT, source),
    ):
        if otype == OWNER_PERSON:
            people[cid].add(oid)
        elif otype == OWNER_EVENT and e_otype == OWNER_PERSON:
            people[cid].add(e_owner)
            linked[cid].add(oid)
        else:
            people[cid].add(None)

    to_link, problems = [], []
    for cid, blob in conn.execute(
        "SELECT CitationID, Fields FROM CitationTable WHERE SourceID = ? ORDER BY CitationID", (source,)
    ):
        if not re.search(item, read_fields(blob).get("SpecificItem", "")):
            continue
        owners = people.get(cid, set())
        if len(owners) != 1 or None in owners:
            problems.append((cid, 0, "linked to no person, or to more than one"))
            continue
        person = next(iter(owners))
        candidates = events.get(person, [])
        primary = [e for e in candidates if e[1]]
        chosen = primary or candidates
        if not candidates:
            problems.append((cid, person, "person has no such event"))
        elif len(chosen) > 1:
            problems.append((cid, person, f"person has {len(chosen)} such events"))
        elif chosen[0][0] in linked[cid]:
            continue  # already linked: nothing to do
        else:
            to_link.append((cid, person, chosen[0][0]))
    return to_link, problems


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="link_citations_to_fact.py PATH_TO_RMTREE")
    parser.add_argument("--source", type=int, required=True)
    parser.add_argument("--fact", type=int, required=True, help="fact type to link to, e.g. 1 Birth")
    parser.add_argument("--item", required=True, help="regex the SpecificItem field must match")
    parser.add_argument("--quality", required=True, help='three characters, e.g. "SIX"')
    parser.add_argument("--folder", default="general", help="output folder")
    parser.add_argument("--apply", action="store_true", help="write the links")
    args = parser.parse_args(sys.argv[2:])
    if not QUALITY.match(args.quality):
        print(f"Quality '{args.quality}' is not information (P/S/~), evidence (D/I/N/~), source (O/X/~)")
        return 1

    conn = connect_readonly(path)
    try:
        to_link, problems = build_links(conn, args.source, args.fact, args.item)
        names = person_names(conn)
        dates = dict(conn.execute("SELECT EventID, Date FROM EventTable"))
    finally:
        conn.close()

    with output_file("link_citations_to_fact", args.folder):
        print(f"Links to add: {len(to_link)}; not linked: {len(problems)}")
        if problems:
            print("\n== Not linked")
            for cid, person, why in problems:
                print(f"   C{cid} {names.get(person, '?')} [P{person}]: {why}")
        print(f"\n== Proposed links (quality {args.quality})")
        for cid, person, eid in to_link:
            print(f"   C{cid} -> E{eid} {dates.get(eid)} {names.get(person, '?')} [P{person}]")
    print(f"{len(to_link)} links to add; {len(problems)} not linked")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    try:
        for cid, _, eid in to_link:
            conn.execute(
                "INSERT INTO CitationLinkTable (CitationID, OwnerType, OwnerID, SortOrder, Quality,"
                " IsPrivate, Flags, UTCModDate) VALUES (?, ?, ?, 0, ?, 0, 0, ?)",
                (cid, OWNER_EVENT, eid, args.quality, stamp),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"Applied: {len(to_link)} citation links added.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
