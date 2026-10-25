"""Set an event's (fact's) place and place detail.

--place is a place (PlaceType 0); --site a place detail (PlaceType 2) under that place, or 0 for none.
--new-site NAME instead uses the detail of that name under the place, made if there is none (as
RootsMagic writes one: Reverse = Name, no coordinates).

Refused: the event, place or detail does not exist, or the detail is not under the place.

Dry run by default: prints old and new place. --apply writes it in one transaction.
RootsMagic must be closed, and the file must be a working copy.

Usage: python set_event_place.py PATH_TO_RMTREE --event ID --place ID [--site ID | --new-site NAME]
           [--apply]
"""

import argparse
import sys

from rmutils import connect_readonly, connect_readwrite, db_path_arg, utc_mod_date

PLACE, DETAIL = 0, 2


def place_name(conn, pid) -> str:
    row = conn.execute("SELECT Name FROM PlaceTable WHERE PlaceID = ?", (pid,)).fetchone()
    return row[0] if row else "-"


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="set_event_place.py PATH_TO_RMTREE")
    parser.add_argument("--event", type=int, required=True)
    parser.add_argument("--place", type=int, required=True)
    sites = parser.add_mutually_exclusive_group()
    sites.add_argument("--site", type=int, default=0)
    sites.add_argument("--new-site")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(sys.argv[2:])

    conn = connect_readonly(path)
    try:
        new_name = None
        if args.new_site:
            row = conn.execute("SELECT PlaceID FROM PlaceTable WHERE PlaceType = ? AND MasterID = ? AND Name = ?",
                               (DETAIL, args.place, args.new_site)).fetchone()
            if row:
                args.site = row[0]
            else:
                new_name = args.new_site
        row = conn.execute("SELECT EventType, OwnerType, OwnerID, PlaceID, SiteID FROM EventTable WHERE EventID = ?",
                           (args.event,)).fetchone()
        place = conn.execute("SELECT PlaceType FROM PlaceTable WHERE PlaceID = ?", (args.place,)).fetchone()
        site = conn.execute("SELECT PlaceType, MasterID FROM PlaceTable WHERE PlaceID = ?",
                            (args.site,)).fetchone() if args.site else (DETAIL, args.place)
        problems = []
        if row is None:
            problems.append(f"E{args.event} not found")
        if place != (PLACE,):
            problems.append(f"L{args.place} is not a place")
        if site != (DETAIL, args.place):
            problems.append(f"L{args.site} is not a detail under L{args.place}")
        if problems:
            print("Not changed: " + "; ".join(problems))
            return 1
        fact, owner_type, owner, old_place, old_site = row
        new_site = f"new detail {new_name}" if new_name else f"L{args.site} {place_name(conn, args.site)}"
        print(f"E{args.event} (fact {fact}, owner type {owner_type} ID {owner}):"
              f" L{old_place} {place_name(conn, old_place)} / L{old_site} {place_name(conn, old_site)}"
              f" -> L{args.place} {place_name(conn, args.place)} / {new_site}")
    finally:
        conn.close()
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0
    conn = connect_readwrite(path)
    try:
        stamp = utc_mod_date()
        if new_name:
            args.site = conn.execute(
                "INSERT INTO PlaceTable (PlaceType, Name, Abbrev, Normalized, Latitude, Longitude, LatLongExact,"
                " MasterID, Note, Reverse, fsID, anID, UTCModDate) VALUES (?, ?, '', '', 0, 0, 0, ?, '', ?, 0, 0, ?)",
                (DETAIL, new_name, args.place, new_name, stamp)).lastrowid
        conn.execute("UPDATE EventTable SET PlaceID = ?, SiteID = ?, UTCModDate = ? WHERE EventID = ?",
                     (args.place, args.site, stamp, args.event))
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
