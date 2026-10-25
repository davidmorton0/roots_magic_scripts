"""List the people a source's citations touch, with their main facts (read-only).

A person is touched when one of the source's citations is linked to them, to their name,
to one of their events, to a family they are a partner in, or to that family's events.
For each person: Birth, Christen and Death events (date, place, citations from every
source), parents, each family they are a partner in with its Marriage events, and the
citations of this source that touch them. Used for step 1.5 of the record clean-up.

Writes the listing to tmp/output/general/<timestamp>_source_<ID>_people.txt.

Usage: python source_people.py PATH_TO_RMTREE SOURCE_ID
"""

import sys
from collections import defaultdict

from rmutils import connect_readonly, db_path_arg, output_file, person_names

OWNER_PERSON, OWNER_FAMILY, OWNER_EVENT, OWNER_NAME = 0, 1, 2, 7
FACT_BIRTH, FACT_DEATH, FACT_CHRISTEN, FACT_MARRIAGE = 1, 2, 3, 300
LIFE_FACTS = {FACT_BIRTH: "Birth", FACT_CHRISTEN: "Christen", FACT_DEATH: "Death"}


class Tree:
    def __init__(self, conn):
        self.conn = conn
        self.names = person_names(conn)
        self.families = {f: (fa, mo) for f, fa, mo in conn.execute("SELECT FamilyID, FatherID, MotherID FROM FamilyTable")}
        self.places = dict(conn.execute("SELECT PlaceID, Name FROM PlaceTable"))
        self.cites = defaultdict(list)
        for cid, oid in conn.execute("SELECT CitationID, OwnerID FROM CitationLinkTable WHERE OwnerType = ?",
                                     (OWNER_EVENT,)):
            self.cites[oid].append(cid)

    def partners(self, family: int) -> list[int]:
        return [p for p in self.families.get(family, (0, 0)) if p]

    def touched(self, owner_type: int, owner_id: int) -> list[int]:
        if owner_type == OWNER_PERSON:
            return [owner_id]
        if owner_type == OWNER_FAMILY:
            return self.partners(owner_id)
        if owner_type == OWNER_NAME:
            row = self.conn.execute("SELECT OwnerID FROM NameTable WHERE NameID = ?", (owner_id,)).fetchone()
            return [row[0]] if row else []
        if owner_type == OWNER_EVENT:
            row = self.conn.execute("SELECT OwnerType, OwnerID FROM EventTable WHERE EventID = ?",
                                    (owner_id,)).fetchone()
            return self.touched(*row) if row else []
        return []

    def event_text(self, eid, date, place, site) -> str:
        where = ", ".join(self.places.get(p, "") for p in (site, place) if p) or "no place"
        cited = ", ".join(f"C{c}" for c in self.cites.get(eid, [])) or "not cited"
        return f"{date} {where} [E{eid}; {cited}]"

    def person_name(self, pid: int) -> str:
        return f"P{pid} {self.names.get(pid, '(missing person)')}" if pid else "?"


def describe(t: Tree, pid: int, citations: list[int]) -> list[str]:
    lines = [f"{t.person_name(pid)} (this source: {', '.join(f'C{c}' for c in citations)})"]
    for fact, eid, date, place, site in t.conn.execute(
            "SELECT EventType, EventID, Date, PlaceID, SiteID FROM EventTable WHERE OwnerType = ? AND OwnerID = ?"
            " AND EventType IN (?, ?, ?) ORDER BY EventType, Date", (OWNER_PERSON, pid, *LIFE_FACTS)):
        lines.append(f"   {LIFE_FACTS[fact]}: {t.event_text(eid, date, place, site)}")
    for (family,) in t.conn.execute("SELECT FamilyID FROM ChildTable WHERE ChildID = ?", (pid,)):
        lines.append(f"   parents F{family}: " + " & ".join(t.person_name(p) for p in t.families.get(family, (0, 0))))
    for family, (father, mother) in t.families.items():
        if pid not in (father, mother):
            continue
        partner = mother if pid == father else father
        lines.append(f"   family F{family} with {t.person_name(partner)}")
        for eid, date, place, site in t.conn.execute(
                "SELECT EventID, Date, PlaceID, SiteID FROM EventTable WHERE OwnerType = ? AND OwnerID = ?"
                " AND EventType = ?", (OWNER_FAMILY, family, FACT_MARRIAGE)):
            lines.append(f"      Marriage: {t.event_text(eid, date, place, site)}")
    return lines


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    if len(sys.argv) < 3 or not sys.argv[2].isdigit():
        print(__doc__.strip().splitlines()[-1])
        return 2
    source_id = int(sys.argv[2])
    conn = connect_readonly(path)
    try:
        name = conn.execute("SELECT Name FROM SourceTable WHERE SourceID = ?", (source_id,)).fetchone()
        if name is None:
            print(f"No source S{source_id}")
            return 1
        t = Tree(conn)
        people = defaultdict(list)
        for cid, owner_type, owner_id in conn.execute(
                "SELECT l.CitationID, l.OwnerType, l.OwnerID FROM CitationLinkTable l JOIN CitationTable c"
                " ON c.CitationID = l.CitationID WHERE c.SourceID = ? ORDER BY l.CitationID", (source_id,)):
            for pid in t.touched(owner_type, owner_id):
                if cid not in people[pid]:
                    people[pid].append(cid)
        with output_file(f"source_{source_id}_people"):
            print(f"S{source_id} {name[0]}: {len(people)} people\n")
            for pid in sorted(people, key=lambda p: (t.names.get(p, "").split()[-1:], p)):
                print("\n".join(describe(t, pid, people[pid])))
                print()
    finally:
        conn.close()
    print(f"S{source_id}: {len(people)} people")
    return 0


if __name__ == "__main__":
    sys.exit(main())
