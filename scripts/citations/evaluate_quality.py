"""Fetch citation links and flag quality ratings that are not set or differ from the ratings table (read-only).

The table is in .claude/skills/rm-evaluate-quality/quality.md (--table FILE for another). Each link
takes the first row whose Name matches its source's name, whose Fact is the linked fact (`family`,
`name`) and whose Condition holds:

  UNRATED  quality not set ("~" in it); the expected rating is given where a row fits
  DIFFERS  quality differs from the row's rating
  NOROW    rated, but no row fits the link (add one to the table)

Writes each flagged link to tmp/output/citations/<timestamp>_evaluate_quality.txt and prints the
counts per source and flag. Fix with records/citation_link.py edit LINK_ID --quality XYZ.

Usage: python evaluate_quality.py PATH_TO_RMTREE (--source ID ... | --citation ID ... | --all) [--table FILE]
"""

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from rmutils import PROJECT_DIR, connect_readonly, db_path_arg, first_row, load_rows, output_file, read_fields

TABLE_FILE = PROJECT_DIR / ".claude" / "skills" / "rm-evaluate-quality" / "quality.md"
OWNER_PERSON, OWNER_FAMILY, OWNER_EVENT, OWNER_NAME = 0, 1, 2, 7
IMAGE_NAME = re.compile(r".* - (Photograph|Photographs|Image)")
IMAGE_FILE = re.compile(r".*\.(jpe?g|tiff?|png|gif|bmp)", re.IGNORECASE)


def holds_images(name: str, source_fields: dict, image_scan: bool) -> bool:
    """O, not X: the source holds images of the record (its Descriptor says so, or it is named "... - Photograph(s)"
    or "... - Image") and the citation has an image scan attached (index entries of such a source have none)."""
    return image_scan and ("image" in source_fields.get("Descriptor", "").casefold() or bool(IMAGE_NAME.fullmatch(name)))


def expected(row: dict, images: bool) -> list[str]:
    return [r.replace("{O/X}", "O" if images else "X") for r in row["Rating"].split("|")]


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="evaluate_quality.py PATH_TO_RMTREE")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--source", type=int, action="append")
    which.add_argument("--citation", type=int, action="append")
    which.add_argument("--all", action="store_true")
    parser.add_argument("--table", type=Path, default=TABLE_FILE)
    args = parser.parse_args(sys.argv[2:])
    rows = load_rows(args.table, "Ratings")

    conn = connect_readonly(path)
    try:
        facts = dict(conn.execute("SELECT FactTypeID, Name FROM FactTypeTable"))
        events = dict(conn.execute("SELECT EventID, EventType FROM EventTable"))
        sql = ("SELECT l.LinkID, l.Quality, l.OwnerType, l.OwnerID, c.CitationID, c.Fields, c.ActualText,"
               " s.SourceID, s.Name, s.TemplateID, s.Fields FROM CitationLinkTable l JOIN CitationTable c"
               " USING (CitationID) JOIN SourceTable s USING (SourceID)")
        if args.all:
            links = conn.execute(sql + " ORDER BY s.SourceID, l.LinkID").fetchall()
        elif args.source:
            links = [r for sid in args.source for r in conn.execute(sql + " WHERE s.SourceID = ? ORDER BY l.LinkID",
                                                                     (sid,))]
        else:
            links = [r for cid in args.citation for r in conn.execute(sql + " WHERE c.CitationID = ? ORDER BY"
                                                                       " l.LinkID", (cid,))]
        image_scans = {cid for cid, file in conn.execute(
            "SELECT l.OwnerID, m.MediaFile FROM MediaLinkTable l JOIN MultimediaTable m USING (MediaID)"
            " WHERE l.OwnerType = 4") if IMAGE_FILE.fullmatch(file or "")}
        known = {r[0] for r in conn.execute("SELECT SourceID FROM SourceTable")} if args.source else \
            {r[0] for r in conn.execute("SELECT CitationID FROM CitationTable")}
    finally:
        conn.close()
    missing = [w for w in (args.source or args.citation or []) if w not in known]
    if missing:
        print("Not found: " + ", ".join(f"{'S' if args.source else 'C'}{m}" for m in missing))
        return 1

    results = []
    for link, quality, otype, oid, cid, cblob, text, sid, source, template, sblob in links:
        kind = facts.get(events.get(oid), "?") if otype == OWNER_EVENT else \
            {OWNER_PERSON: "person", OWNER_FAMILY: "family", OWNER_NAME: "name"}.get(otype, f"type {otype}")
        fields = read_fields(cblob)
        row = first_row(rows, source or "", fields, text or "", lambda r: kind in r["Fact"].split("|"))
        want = expected(row, holds_images(source or "", read_fields(sblob), cid in image_scans)) if row else []
        quality = quality or "~~~"
        if "~" in quality:
            flag = "UNRATED " + (f"expected {' or '.join(want)} ({row['Record']})" if row else "no row fits")
        elif row and quality not in want:
            flag = f"DIFFERS {quality}; expected {' or '.join(want)} ({row['Record']})"
        elif not row:
            flag = f"NOROW {quality}: no row in quality.md fits {kind}"
        else:
            flag = ""
        results.append((sid, source, cid, link, kind, oid, quality, flag))

    with output_file("evaluate_quality", "citations"):
        print(f"File: {path}\nTable: {args.table}\n")
        for sid, source, cid, link, kind, oid, quality, flag in results:
            if flag:
                print(f"S{sid} C{cid} L{link} -> {kind} {oid}: {flag}")
    by_source = defaultdict(list)
    for result in results:
        by_source[(result[0], result[1])].append(result)
    for (sid, source), group in by_source.items():
        counts = Counter(r[7].split()[0] for r in group if r[7])
        print(f"S{sid} '{source}': {len(group)} links, {sum(counts.values())} flagged"
              + ("; " + ", ".join(f"{c} {n}" for c, n in sorted(counts.items())) if counts else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
