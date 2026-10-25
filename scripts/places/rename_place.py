"""Rename a place or place detail; every fact using it follows.

The sort name (Reverse) changes with it: for a place, the name's comma-separated parts in
reverse order ("Ilkeston, Derbyshire, England" -> "England, Derbyshire, Ilkeston"), as
RootsMagic writes it; for a place detail, the new name if Reverse held the old name, else
left as it is (details made by hand hold their name there, others nothing). Refused if
another place (or another detail under the same place) already has the new name.

Name is in an RMNOCASE index: run RootsMagic's rebuild indexes after.

Dry run by default. --apply writes it in one transaction. RootsMagic must be closed, and
the file must be a working copy.

Usage: python rename_place.py PATH_TO_RMTREE --place ID --name NEW_NAME [--apply]
"""

import argparse
import sys

from rmutils import connect_readonly, connect_readwrite, db_path_arg, utc_mod_date

PLACE_DETAIL = 2


def reverse_name(name: str) -> str:
    return ", ".join(part.strip() for part in reversed(name.split(",")))


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="rename_place.py PATH_TO_RMTREE")
    parser.add_argument("--place", type=int, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(sys.argv[2:])

    conn = connect_readonly(path)
    try:
        row = conn.execute("SELECT Name, PlaceType, MasterID, Reverse FROM PlaceTable WHERE PlaceID = ?",
                           (args.place,)).fetchone()
        if row is None:
            print(f"Not changed: no place L{args.place}")
            return 1
        old, place_type, master, reverse = row
        if place_type == PLACE_DETAIL:
            clash = conn.execute("SELECT PlaceID FROM PlaceTable WHERE PlaceType = ? AND MasterID = ? AND Name = ?"
                                 " AND PlaceID != ?", (PLACE_DETAIL, master, args.name, args.place)).fetchall()
        else:
            clash = conn.execute("SELECT PlaceID FROM PlaceTable WHERE PlaceType = ? AND Name = ? AND PlaceID != ?",
                                 (place_type, args.name, args.place)).fetchall()
        uses = conn.execute("SELECT COUNT(*) FROM EventTable WHERE PlaceID = ? OR SiteID = ?",
                            (args.place, args.place)).fetchone()[0]
    finally:
        conn.close()
    if clash:
        print(f"Not changed: {args.name!r} already used by {', '.join(f'L{r[0]}' for r in clash)}")
        return 1
    if place_type == PLACE_DETAIL:
        new_reverse = args.name if reverse == old else reverse
    else:
        new_reverse = reverse_name(args.name)
    print(f"L{args.place}: {old!r} -> {args.name!r}; sort name {reverse!r} -> {new_reverse!r}; used by {uses} facts")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0
    conn = connect_readwrite(path)
    try:
        conn.execute("UPDATE PlaceTable SET Name = ?, Reverse = ?, UTCModDate = ? WHERE PlaceID = ?",
                     (args.name, new_reverse, utc_mod_date(), args.place))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print("Applied. Run RootsMagic's rebuild indexes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
