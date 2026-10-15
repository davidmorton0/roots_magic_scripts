"""Delete a source that nothing uses.

Refuses if the source has citations, or media, tasks, web links or addresses
attached to it (OwnerType 3).

Dry run by default: prints what would be deleted. --apply deletes it.
RootsMagic must be closed, and the file must be a working copy.

Usage: python delete_source.py PATH_TO_RMTREE SOURCE_ID [--apply]
"""

import argparse
import sys

from rmutils import connect_readonly, connect_readwrite, db_path_arg

OWNER_SOURCE = 3
USES = {
    "citations": "SELECT COUNT(*) FROM CitationTable WHERE SourceID = ?",
    "media": "SELECT COUNT(*) FROM MediaLinkTable WHERE OwnerType = 3 AND OwnerID = ?",
    "tasks": "SELECT COUNT(*) FROM TaskLinkTable WHERE OwnerType = 3 AND OwnerID = ?",
    "web links": "SELECT COUNT(*) FROM URLTable WHERE OwnerType = 3 AND OwnerID = ?",
    "addresses": "SELECT COUNT(*) FROM AddressLinkTable WHERE OwnerType = 3 AND OwnerID = ?",
}


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="delete_source.py PATH_TO_RMTREE")
    parser.add_argument("source", type=int)
    parser.add_argument("--apply", action="store_true", help="delete the source")
    args = parser.parse_args(sys.argv[2:])

    conn = connect_readonly(path)
    try:
        row = conn.execute("SELECT Name FROM SourceTable WHERE SourceID = ?", (args.source,)).fetchone()
        uses = {kind: conn.execute(sql, (args.source,)).fetchone()[0] for kind, sql in USES.items()}
    finally:
        conn.close()
    if row is None:
        print(f"Source S{args.source} not found")
        return 1
    used = {k: n for k, n in uses.items() if n}
    if used:
        print(f"S{args.source} '{row[0]}' is still used: {used}")
        return 1

    print(f"Delete S{args.source} '{row[0]}' (no citations or attachments)")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0
    conn = connect_readwrite(path)
    try:
        conn.execute("DELETE FROM SourceTable WHERE SourceID = ?", (args.source,))
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
