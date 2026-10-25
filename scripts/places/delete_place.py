"""Delete a place or place detail that nothing uses.

Refused if any fact (EventTable PlaceID or SiteID) or FAN row uses it, or any place
detail sits under it.

Dry run by default. --apply writes it in one transaction. RootsMagic must be closed, and
the file must be a working copy.

Usage: python delete_place.py PATH_TO_RMTREE --place ID [--apply]
"""

import argparse
import sys

from rmutils import connect_readonly, connect_readwrite, db_path_arg


def uses(conn, pid: int) -> dict[str, int]:
    return {
        "facts": conn.execute("SELECT COUNT(*) FROM EventTable WHERE PlaceID = ? OR SiteID = ?",
                              (pid, pid)).fetchone()[0],
        "FAN rows": conn.execute("SELECT COUNT(*) FROM FANTable WHERE PlaceID = ? OR SiteID = ?",
                                 (pid, pid)).fetchone()[0],
        "place details": conn.execute("SELECT COUNT(*) FROM PlaceTable WHERE MasterID = ?", (pid,)).fetchone()[0],
    }


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="delete_place.py PATH_TO_RMTREE")
    parser.add_argument("--place", type=int, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(sys.argv[2:])

    conn = connect_readonly(path)
    try:
        row = conn.execute("SELECT Name FROM PlaceTable WHERE PlaceID = ?", (args.place,)).fetchone()
        used = uses(conn, args.place) if row else {}
    finally:
        conn.close()
    if row is None:
        print(f"Not changed: no place L{args.place}")
        return 1
    if any(used.values()):
        print(f"Not changed: L{args.place} {row[0]!r} is used ({used})")
        return 1
    print(f"Delete L{args.place} {row[0]!r} (unused)")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0
    conn = connect_readwrite(path)
    try:
        conn.execute("DELETE FROM PlaceTable WHERE PlaceID = ?", (args.place,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"Applied: L{args.place} deleted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
