"""Set an event's (fact's) date, in RootsMagic's encoded form, and its SortDate.

The date is given encoded, e.g. D.+18920421..+00000000.. (single), DB+18860400..+00000000..
(before) or DR+19000900..+19010800.. (between); SortDate comes from rmutils.sort_date, so
dates it cannot sort (no year, double-dated, DS) are refused.

Dry run by default: prints old and new date. --apply writes it in one transaction.
RootsMagic must be closed, and the file must be a working copy.

Usage: python set_event_date.py PATH_TO_RMTREE --event ID --date ENCODED [--apply]
"""

import argparse
import sys

from rmutils import connect_readonly, connect_readwrite, db_path_arg, sort_date, utc_mod_date


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="set_event_date.py PATH_TO_RMTREE")
    parser.add_argument("--event", type=int, required=True)
    parser.add_argument("--date", required=True, help="encoded, e.g. DR+19000900..+19010800..")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(sys.argv[2:])
    sort = sort_date(args.date)
    if sort is None:
        print(f"Not changed: no SortDate for {args.date!r}")
        return 1

    conn = connect_readonly(path)
    try:
        row = conn.execute("SELECT EventType, OwnerType, OwnerID, Date FROM EventTable WHERE EventID = ?",
                           (args.event,)).fetchone()
    finally:
        conn.close()
    if row is None:
        print(f"Not changed: E{args.event} not found")
        return 1
    fact, owner_type, owner, old = row
    print(f"E{args.event} (fact {fact}, owner type {owner_type} ID {owner}): {old} -> {args.date} (SortDate {sort})")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0
    conn = connect_readwrite(path)
    try:
        conn.execute("UPDATE EventTable SET Date = ?, SortDate = ?, UTCModDate = ? WHERE EventID = ?",
                     (args.date, sort, utc_mod_date(), args.event))
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
