"""Set an event's (fact's) note, replacing what it holds.

Dry run by default: prints old and new note. --apply writes it in one transaction.
RootsMagic must be closed, and the file must be a working copy.

Usage: python set_event_note.py PATH_TO_RMTREE --event ID --note TEXT [--apply]
"""

import argparse
import sys

from rmutils import connect_readonly, connect_readwrite, db_path_arg, utc_mod_date


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="set_event_note.py PATH_TO_RMTREE")
    parser.add_argument("--event", type=int, required=True)
    parser.add_argument("--note", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(sys.argv[2:])

    conn = connect_readonly(path)
    try:
        row = conn.execute("SELECT EventType, OwnerType, OwnerID, Note FROM EventTable WHERE EventID = ?",
                           (args.event,)).fetchone()
    finally:
        conn.close()
    if row is None:
        print(f"Not changed: E{args.event} not found")
        return 1
    fact, owner_type, owner, old = row
    print(f"E{args.event} (fact {fact}, owner type {owner_type} ID {owner}):\n   old: {old!r}\n   new: {args.note!r}")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0
    conn = connect_readwrite(path)
    try:
        conn.execute("UPDATE EventTable SET Note = ?, UTCModDate = ? WHERE EventID = ?",
                     (args.note, utc_mod_date(), args.event))
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
