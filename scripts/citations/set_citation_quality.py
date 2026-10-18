"""Set the quality of citation links that are still unassessed.

CitationLinkTable.Quality holds three characters, as RootsMagic 12 wrote them
when set by hand (2026-10-15):
  1 information  P primary, S secondary, ~ not set
  2 evidence     D direct, I indirect, N negative, ~ not set
  3 source       O original (not seen yet), X derivative, ~ not set
"PIX" = primary information, indirect evidence, derivative source.

For every link of the given sources' citations whose quality is "~~~", set
--quality. Links with any other value are left alone and counted.
--fact ID limits it to links to events of that fact type (e.g. 2 Death);
--item REGEX to citations whose SpecificItem field matches (re.search), and
--not-item REGEX to those whose SpecificItem does not.

Dry run by default: prints what would change. --apply writes it in one
transaction. RootsMagic must be closed, and the file must be a working copy.

Usage: python set_citation_quality.py PATH_TO_RMTREE --source ID [ID ...] --quality XYZ
           [--fact ID] [--item REGEX] [--not-item REGEX] [--apply]
"""

import argparse
import re
import sys
from collections import Counter

from rmutils import connect_readonly, connect_readwrite, db_path_arg, read_fields, utc_mod_date

OWNER_EVENT = 2
UNSET = "~~~"
QUALITY = re.compile(r"^[PS~][DIN~][OX~]$")


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="set_citation_quality.py PATH_TO_RMTREE")
    parser.add_argument("--source", type=int, nargs="+", required=True)
    parser.add_argument("--quality", required=True, help='three characters, e.g. "PIX"')
    parser.add_argument("--fact", type=int, help="only links to events of this fact type")
    parser.add_argument("--item", help="only citations whose SpecificItem matches this regex")
    parser.add_argument("--not-item", help="only citations whose SpecificItem does not match")
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])
    if not QUALITY.match(args.quality):
        print(f"Quality '{args.quality}' is not information (P/S/~), evidence (D/I/N/~), source (O/X/~)")
        return 1

    marks = ",".join("?" * len(args.source))
    conn = connect_readonly(path)
    try:
        rows = conn.execute(
            f"""SELECT cl.LinkID, cl.Quality, cl.OwnerType, cl.OwnerID, c.Fields
                FROM CitationLinkTable cl
                JOIN CitationTable c USING (CitationID) WHERE c.SourceID IN ({marks})
                ORDER BY cl.LinkID""",
            args.source,
        ).fetchall()
        event_types = dict(conn.execute("SELECT EventID, EventType FROM EventTable")) if args.fact else {}
    finally:
        conn.close()

    links = []
    for link_id, quality, owner_type, owner_id, blob in rows:
        if args.fact and not (owner_type == OWNER_EVENT and event_types.get(owner_id) == args.fact):
            continue
        if args.item or args.not_item:
            item = read_fields(blob).get("SpecificItem", "")
            if args.item and not re.search(args.item, item):
                continue
            if args.not_item and re.search(args.not_item, item):
                continue
        links.append((link_id, quality))

    to_set = [link_id for link_id, quality in links if (quality or UNSET) == UNSET]
    kept = Counter(quality for _, quality in links if (quality or UNSET) != UNSET)
    print(f"Citation links: {len(links)}; set to '{args.quality}': {len(to_set)};"
          f" already assessed, kept: {sum(kept.values())} {dict(kept)}")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    try:
        for link_id in to_set:
            conn.execute(
                "UPDATE CitationLinkTable SET Quality = ?, UTCModDate = ? WHERE LinkID = ? AND Quality = ?",
                (args.quality, stamp, link_id, UNSET),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"Applied: {len(to_set)} citation links set.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
