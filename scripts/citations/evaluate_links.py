"""Fetch citations with their links and flag links missing or not allowed for the record type (read-only).

The table is in .claude/skills/rm-evaluate-links/facts_cited.md (--table FILE for another). Each
citation takes the first row whose Name matches its source's name and whose Condition holds:

  NOROW    no row fits the citation (add one to the table)
  MISSING  a required fact (or a conditional one whose condition holds) is not linked; for each
           person the citation touches, names the fact to link, or says it must be created (G8)
  EXTRA    linked to a fact the record type does not support (G7, G17)
  G7       linked to a record event (fact 1000 and over)
  G17      linked to a person as a whole

Writes each flagged citation to tmp/output/citations/<timestamp>_evaluate_links.txt and prints the
counts per source and flag.

Usage: python evaluate_links.py PATH_TO_RMTREE (--source ID ... | --citation ID ... | --all) [--table FILE]
"""

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from rmutils import PROJECT_DIR, condition_holds, connect_readonly, db_path_arg, first_row, load_rows, output_file, \
    person_names, read_fields

TABLE_FILE = PROJECT_DIR / ".claude" / "skills" / "rm-evaluate-links" / "facts_cited.md"
OWNER_PERSON, OWNER_FAMILY, OWNER_EVENT, OWNER_NAME = 0, 1, 2, 7
FIRST_RECORD_FACT = 1000
ITEM = re.compile(r"(.+?) if (\w+~.+)")


def parse_facts(cell: str) -> list[tuple[str, str]]:
    """'Birth if SpecificItem~age, name' -> [('Birth', 'SpecificItem~age'), ('name', '')]."""
    items = []
    for item in filter(None, (i.strip() for i in cell.split(", "))):
        match = ITEM.fullmatch(item)
        items.append((match.group(1), match.group(2)) if match else (item, ""))
    return items


class Tree:
    def __init__(self, conn):
        self.conn = conn
        self.names = person_names(conn)
        self.facts = dict(conn.execute("SELECT FactTypeID, Name FROM FactTypeTable"))
        self.fact_ids = {name: fid for fid, name in self.facts.items()}
        self.families = {f: (a, b) for f, a, b in conn.execute("SELECT FamilyID, FatherID, MotherID FROM FamilyTable")}
        self.events = {e: (t, ot, o, d) for e, t, ot, o, d in conn.execute(
            "SELECT EventID, EventType, OwnerType, OwnerID, Date FROM EventTable")}

    def people(self, links) -> set[int]:
        """The record's own people: from person, name and person-event links; failing those, the
        partners of linked families (and of family events)."""
        own, partners = set(), set()
        for otype, oid in links:
            if otype == OWNER_EVENT and oid in self.events:
                otype, oid = self.events[oid][1:3]
            if otype == OWNER_PERSON:
                own.add(oid)
            elif otype == OWNER_NAME:
                own |= {r[0] for r in self.conn.execute("SELECT OwnerID FROM NameTable WHERE NameID = ?", (oid,))}
            elif otype == OWNER_FAMILY:
                partners |= {p for p in self.families.get(oid, ()) if p}
        return own or partners

    def kind(self, otype: int, oid: int) -> str:
        if otype == OWNER_EVENT:
            return self.facts.get(self.events.get(oid, (None,))[0], "?")
        return {OWNER_PERSON: "person", OWNER_FAMILY: "family", OWNER_NAME: "name"}.get(otype, f"type {otype}")

    def suggestion(self, fact: str, people: set[int]) -> str:
        """Where a missing fact is, or that it is missing, for each person the citation touches."""
        if not people:
            return "no person linked to look on"
        parts = []
        for pid in sorted(people):
            who = f"P{pid} {self.names.get(pid, '?')}"
            families = [f for f, pair in self.families.items() if pid in pair]
            if fact == "family":
                parts.append(f"{who}: families {', '.join(f'F{f}' for f in families) or 'none'}")
                continue
            fid = self.fact_ids.get(fact)
            owned = [(e, d) for e, (t, ot, o, d) in self.events.items() if t == fid and (
                (ot == OWNER_PERSON and o == pid) or (ot == OWNER_FAMILY and o in families))]
            parts.append(f"{who}: " + (", ".join(f"E{e} ({d}) - link it" for e, d in owned) if owned
                                       else f"no {fact} - create it (G8)"))
        return "; ".join(parts)


def evaluate(tree: Tree, rows, source: str, fields: dict, text: str, links: list[tuple[int, int, int]]) -> list[str]:
    flags = []
    row = first_row(rows, source, fields, text)
    pairs = [(otype, oid) for _, otype, oid in links]
    linked = Counter(tree.kind(otype, oid) for otype, oid in pairs)
    for _, otype, oid in links:
        if otype == OWNER_EVENT and tree.events.get(oid, (0,))[0] >= FIRST_RECORD_FACT:
            flags.append(f"G7 linked to record event E{oid} ({tree.kind(otype, oid)})")
        elif otype == OWNER_PERSON:
            flags.append(f"G17 linked to person P{oid} {tree.names.get(oid, '?')} as a whole")
    if row is None:
        return flags + ["NOROW no row in facts_cited.md fits this citation"]
    required = parse_facts(row["Required"])
    optional = parse_facts(row["Optional"])
    needed = [f for f, _ in required] + [f for f, cond in optional if cond and condition_holds(cond, fields, text)]
    people = tree.people(pairs)
    for fact in needed:
        if not linked.get(fact):
            flags.append(f"MISSING {fact}: {tree.suggestion(fact, people)}")
    allowed = {f for f, _ in required + optional}
    if "*" not in allowed:
        for kind in sorted(linked):
            if kind not in allowed and kind != "person" and not kind.startswith("type "):
                record = tree.fact_ids.get(kind, 0) >= FIRST_RECORD_FACT
                if not record:
                    flags.append(f"EXTRA linked to {kind} ({linked[kind]}), not a fact '{row['Record type']}' supports")
    return flags


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="evaluate_links.py PATH_TO_RMTREE")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--source", type=int, action="append")
    which.add_argument("--citation", type=int, action="append")
    which.add_argument("--all", action="store_true")
    parser.add_argument("--table", type=Path, default=TABLE_FILE)
    args = parser.parse_args(sys.argv[2:])
    rows = load_rows(args.table, "Facts cited")

    conn = connect_readonly(path)
    try:
        sql = ("SELECT c.CitationID, c.SourceID, s.Name, c.Fields, c.ActualText FROM CitationTable c"
               " JOIN SourceTable s USING (SourceID)")
        if args.all:
            citations = conn.execute(sql + " ORDER BY c.SourceID, c.CitationID").fetchall()
        elif args.source:
            citations = [r for sid in args.source for r in conn.execute(sql + " WHERE c.SourceID = ?"
                                                                         " ORDER BY c.CitationID", (sid,))]
        else:
            citations = [r for cid in args.citation for r in conn.execute(sql + " WHERE c.CitationID = ?", (cid,))]
        wanted = args.source or args.citation or []
        found = {r[1] for r in citations} if args.source else {r[0] for r in citations}
        missing = [w for w in wanted if w not in found]
        if missing:
            print("Not found: " + ", ".join(f"{'S' if args.source else 'C'}{m}" for m in missing))
            return 1
        tree = Tree(conn)
        results = []
        for cid, sid, source, blob, text in citations:
            links = conn.execute("SELECT LinkID, OwnerType, OwnerID FROM CitationLinkTable WHERE CitationID = ?"
                                 " ORDER BY LinkID", (cid,)).fetchall()
            fields = read_fields(blob)
            flags = evaluate(tree, rows, source or "", fields, text or "", links)
            row = first_row(rows, source or "", fields, text or "")
            linked = ", ".join(f"{tree.kind(o, i)} {'E' if o == OWNER_EVENT else ''}{i}" for _, o, i in links)
            results.append((cid, sid, source, row["Record type"] if row else "no row", fields, linked, flags))
    finally:
        conn.close()

    with output_file("evaluate_links", "citations"):
        print(f"File: {path}\nTable: {args.table}\n")
        for cid, sid, source, kind, fields, linked, flags in results:
            if flags or args.citation:
                print(f"C{cid}  S{sid} '{source}'  [{kind}]")
                print(f"   entry: {fields.get('SpecificItem') or fields.get('Page') or ''!r}")
                print(f"   linked: {linked or 'nothing'}")
                for flag in flags or ["(no flags)"]:
                    print(f"   ! {flag}")
                print()
    by_source = defaultdict(list)
    for result in results:
        by_source[(result[1], result[2])].append(result)
    for (sid, source), group in by_source.items():
        counts = Counter(flag.split()[0] for r in group for flag in r[6])
        print(f"S{sid} '{source}': {len(group)} citations, {sum(1 for r in group if r[6])} flagged"
              + ("; " + ", ".join(f"{c} {n}" for c, n in sorted(counts.items())) if counts else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
