"""Merge one place (or place detail) into another, then delete the emptied one.

Both must be the same kind: two places, or two place details.
  places:  facts (EventTable PlaceID) and FAN rows move to the kept place; place details
           under the merged place move under the kept one (refused if one has the same
           name as a detail already there)
  details: facts (EventTable SiteID) and FAN rows move to the kept detail; they also
           take the kept detail's place, if it sits under another one
Refused if the merged place holds a note or a map position, which would be lost.

Name is in an RMNOCASE index: run RootsMagic's rebuild indexes after.

Dry run by default. --apply writes it in one transaction. RootsMagic must be closed, and
the file must be a working copy.

Usage: python merge_places.py PATH_TO_RMTREE --merge ID --into ID [--apply]
"""

import argparse
import sys

from rmutils import connect_readonly, connect_readwrite, db_path_arg, utc_mod_date

PLACE_DETAIL = 2


def place_row(conn, pid):
    return conn.execute("SELECT Name, PlaceType, MasterID, Note, Latitude, Longitude FROM PlaceTable"
                        " WHERE PlaceID = ?", (pid,)).fetchone()


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="merge_places.py PATH_TO_RMTREE")
    parser.add_argument("--merge", type=int, required=True, help="place to merge and delete")
    parser.add_argument("--into", type=int, required=True, help="place to keep")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(sys.argv[2:])
    drop, keep = args.merge, args.into

    conn = connect_readonly(path)
    try:
        d, k = place_row(conn, drop), place_row(conn, keep)
        problems = []
        if d is None or k is None or drop == keep:
            problems.append(f"need two different existing places (L{drop}: {d}, L{keep}: {k})")
        else:
            if (d[1] == PLACE_DETAIL) != (k[1] == PLACE_DETAIL):
                problems.append("one is a place and the other a place detail")
            if d[3] or d[4] or d[5]:
                problems.append(f"L{drop} holds a note or a map position")
            if d[1] != PLACE_DETAIL:
                kept_names = {r[0] for r in conn.execute("SELECT Name FROM PlaceTable WHERE MasterID = ?", (keep,))}
                same = [r[0] for r in conn.execute("SELECT Name FROM PlaceTable WHERE MasterID = ?", (drop,))
                        if r[0] in kept_names]
                if same:
                    problems.append(f"details under both places: {same}")
        if problems:
            print("Not changed: " + "; ".join(problems))
            return 1
        column = "SiteID" if d[1] == PLACE_DETAIL else "PlaceID"
        facts = conn.execute(f"SELECT COUNT(*) FROM EventTable WHERE {column} = ?", (drop,)).fetchone()[0]
        fan = conn.execute(f"SELECT COUNT(*) FROM FANTable WHERE {column} = ?", (drop,)).fetchone()[0]
        details = 0 if d[1] == PLACE_DETAIL else conn.execute(
            "SELECT COUNT(*) FROM PlaceTable WHERE MasterID = ?", (drop,)).fetchone()[0]
    finally:
        conn.close()
    print(f"L{drop} {d[0]!r} into L{keep} {k[0]!r}: {facts} facts, {fan} FAN rows"
          + (f", {details} place details" if details else "") + f" move; L{drop} deleted")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0
    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    try:
        if d[1] == PLACE_DETAIL:
            for table in ("EventTable", "FANTable"):
                conn.execute(f"UPDATE {table} SET SiteID = ?, PlaceID = ?, UTCModDate = ? WHERE SiteID = ?",
                             (keep, k[2], stamp, drop))
        else:
            for table in ("EventTable", "FANTable"):
                conn.execute(f"UPDATE {table} SET PlaceID = ?, UTCModDate = ? WHERE PlaceID = ?", (keep, stamp, drop))
            conn.execute("UPDATE PlaceTable SET MasterID = ?, UTCModDate = ? WHERE MasterID = ?", (keep, stamp, drop))
        conn.execute("DELETE FROM PlaceTable WHERE PlaceID = ?", (drop,))
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
