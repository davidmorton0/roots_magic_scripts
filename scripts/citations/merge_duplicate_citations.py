"""Merge duplicate citations: the same entry cited twice on the same record.

Within the given sources, citations are duplicates when they have the same
source, the same fields (Fields), the same transcription (ActualText, compared
with runs of spaces and tabs as one space) and the same comments, and share at
least one linked record. In each group the lowest CitationID is kept. For each
other citation: its links to records and its media links that the kept one
does not already have are moved to the kept one; the rest, and the citation
itself, are deleted.

Dry run by default: prints what would change. --apply writes it in one
transaction. RootsMagic must be closed, and the file must be a working copy.

Usage: python merge_duplicate_citations.py PATH_TO_RMTREE --source ID [ID ...] [--apply]
"""

import argparse
import re
import sys
from collections import defaultdict

from rmutils import connect_readonly, connect_readwrite, db_path_arg, utc_mod_date

OWNER_CITATION = 4
SPACES = re.compile(r"[ \t]+")


def find_groups(conn, sources: list[int]) -> list[list[int]]:
    marks = ",".join("?" * len(sources))
    content = {}
    for cid, sid, blob, text, comments in conn.execute(
        f"SELECT CitationID, SourceID, Fields, ActualText, Comments FROM CitationTable"
        f" WHERE SourceID IN ({marks})",
        sources,
    ):
        text = SPACES.sub(" ", (text or "").replace("\r", "")).strip()
        content[cid] = (sid, bytes(blob or b""), text, comments or "")
    owners = defaultdict(set)
    for cid, otype, oid in conn.execute("SELECT CitationID, OwnerType, OwnerID FROM CitationLinkTable"):
        if cid in content:
            owners[(otype, oid)].add(cid)
    groups, seen = [], set()
    for cids in owners.values():
        by_content = defaultdict(list)
        for cid in sorted(cids):
            by_content[content[cid]].append(cid)
        for group in by_content.values():
            if len(group) > 1 and tuple(group) not in seen:
                seen.add(tuple(group))
                groups.append(group)
    return groups


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="merge_duplicate_citations.py PATH_TO_RMTREE")
    parser.add_argument("--source", type=int, nargs="+", required=True)
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])

    conn = connect_readonly(path)
    try:
        groups = find_groups(conn, args.source)
        links = defaultdict(list)
        for link_id, cid, otype, oid in conn.execute(
            "SELECT LinkID, CitationID, OwnerType, OwnerID FROM CitationLinkTable"
        ):
            links[cid].append((link_id, otype, oid))
        media = defaultdict(list)
        for link_id, mid, cid in conn.execute(
            "SELECT LinkID, MediaID, OwnerID FROM MediaLinkTable WHERE OwnerType = ?",
            (OWNER_CITATION,),
        ):
            media[cid].append((link_id, mid))
        names = dict(conn.execute("SELECT CitationID, CitationName FROM CitationTable"))
    finally:
        conn.close()

    actions = []  # (kind, id, detail)
    for group in groups:
        keep, *drop = group
        print(f"Keep C{keep}: {names.get(keep, '')}")
        kept_owners = {(t, o) for _, t, o in links[keep]}
        kept_media = {m for _, m in media[keep]}
        for cid in drop:
            for link_id, otype, oid in links[cid]:
                if (otype, oid) in kept_owners:
                    actions.append(("delete link", link_id, cid))
                else:
                    actions.append(("move link", link_id, keep))
                    kept_owners.add((otype, oid))
            for link_id, mid in media[cid]:
                if mid in kept_media:
                    actions.append(("delete media link", link_id, cid))
                else:
                    actions.append(("move media link", link_id, keep))
                    kept_media.add(mid)
            actions.append(("delete citation", cid, keep))
            print(f"   delete C{cid}: links {[l for l, _, _ in links[cid]]},"
                  f" media links {[l for l, _ in media[cid]]}")
    moves = [a for a in actions if a[0].startswith("move")]
    print(f"{len(groups)} duplicate groups; {sum(1 for a in actions if a[0] == 'delete citation')}"
          f" citations to delete; {len(moves)} links to move")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    try:
        for kind, row_id, target in actions:
            if kind == "move link":
                conn.execute("UPDATE CitationLinkTable SET CitationID = ?, UTCModDate = ? WHERE LinkID = ?",
                             (target, stamp, row_id))
            elif kind == "delete link":
                conn.execute("DELETE FROM CitationLinkTable WHERE LinkID = ?", (row_id,))
            elif kind == "move media link":
                conn.execute("UPDATE MediaLinkTable SET OwnerID = ?, UTCModDate = ? WHERE LinkID = ?",
                             (target, stamp, row_id))
            elif kind == "delete media link":
                conn.execute("DELETE FROM MediaLinkTable WHERE LinkID = ?", (row_id,))
            elif kind == "delete citation":
                conn.execute("DELETE FROM CitationTable WHERE CitationID = ?", (row_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print("Applied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
