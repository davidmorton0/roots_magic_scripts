"""Resolve "one of two possible" index entries: keep one citation, delete the other.

Deletes --drop with its links to records and media. Media it shared with --keep
stay attached to --keep; media attached only to --drop are moved to --keep.
The kept citation's Comments (citation note) are replaced with --note, which
should say how the entry was confirmed.

Dry run by default: prints what would change. --apply writes it in one
transaction. RootsMagic must be closed, and the file must be a working copy.

Usage: python resolve_possible_entries.py PATH_TO_RMTREE --keep CITATION_ID
           --drop CITATION_ID --note TEXT [--apply]
"""

import argparse
import sys

from rmutils import connect_readonly, connect_readwrite, db_path_arg, utc_mod_date

OWNER_CITATION = 4


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="resolve_possible_entries.py PATH_TO_RMTREE")
    parser.add_argument("--keep", type=int, required=True)
    parser.add_argument("--drop", type=int, required=True)
    parser.add_argument("--note", required=True)
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])

    conn = connect_readonly(path)
    try:
        rows = dict(conn.execute(
            "SELECT CitationID, CitationName FROM CitationTable WHERE CitationID IN (?, ?)",
            (args.keep, args.drop),
        ))
        comments = conn.execute(
            "SELECT Comments FROM CitationTable WHERE CitationID = ?", (args.keep,)
        ).fetchone()
        drop_links = conn.execute(
            "SELECT LinkID, OwnerType, OwnerID FROM CitationLinkTable WHERE CitationID = ?",
            (args.drop,),
        ).fetchall()
        keep_owners = set(conn.execute(
            "SELECT OwnerType, OwnerID FROM CitationLinkTable WHERE CitationID = ?", (args.keep,)
        ).fetchall())
        drop_media = conn.execute(
            "SELECT LinkID, MediaID FROM MediaLinkTable WHERE OwnerType = ? AND OwnerID = ?",
            (OWNER_CITATION, args.drop),
        ).fetchall()
        keep_media = {mid for (mid,) in conn.execute(
            "SELECT MediaID FROM MediaLinkTable WHERE OwnerType = ? AND OwnerID = ?",
            (OWNER_CITATION, args.keep),
        )}
    finally:
        conn.close()

    if args.keep not in rows or args.drop not in rows:
        print(f"Citation C{args.keep} or C{args.drop} not found")
        return 1
    if not {(t, o) for _, t, o in drop_links} <= keep_owners:
        print(f"C{args.drop} is linked to records C{args.keep} is not; resolve by hand")
        return 1

    move_media = [(l, m) for l, m in drop_media if m not in keep_media]
    print(f"Keep   C{args.keep}: {rows[args.keep]}")
    print(f"   note: '{comments[0] or ''}' -> '{args.note}'")
    print(f"Delete C{args.drop}: {rows[args.drop]}")
    print(f"   citation links {[l for l, _, _ in drop_links]};"
          f" media links deleted {[l for l, m in drop_media if m in keep_media]};"
          f" media moved to C{args.keep} {[m for _, m in move_media]}")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    try:
        conn.execute("UPDATE CitationTable SET Comments = ?, UTCModDate = ? WHERE CitationID = ?",
                     (args.note, stamp, args.keep))
        for link_id, _ in move_media:
            conn.execute("UPDATE MediaLinkTable SET OwnerID = ?, UTCModDate = ? WHERE LinkID = ?",
                         (args.keep, stamp, link_id))
        conn.execute("DELETE FROM MediaLinkTable WHERE OwnerType = ? AND OwnerID = ?",
                     (OWNER_CITATION, args.drop))
        conn.execute("DELETE FROM CitationLinkTable WHERE CitationID = ?", (args.drop,))
        conn.execute("DELETE FROM CitationTable WHERE CitationID = ?", (args.drop,))
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
