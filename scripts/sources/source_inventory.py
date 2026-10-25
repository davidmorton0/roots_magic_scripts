"""List one source with everything attached to it (read-only).

For the source: name, template, Fields values, text and comments. For each of its
citations: CitationName, Fields values, transcription (ActualText), note (Comments),
every citation link (event links with fact name, owner, date, place and place detail;
other links as owner type and ID) with its quality, and the scans linked to it.
Ends with a count of event links per fact type. Used for step 1 (inventory) of the
record clean-up.

Writes the listing to tmp/output/general/<timestamp>_source_<ID>_inventory.txt.

Usage: python source_inventory.py PATH_TO_RMTREE SOURCE_ID
"""

import sys
from collections import Counter

from rmutils import connect_readonly, db_path_arg, output_file, person_names, read_fields

OWNER_PERSON, OWNER_EVENT, OWNER_CITATION = 0, 2, 4


def place_name(conn, place_id) -> str:
    if not place_id:
        return "-"
    row = conn.execute("SELECT Name FROM PlaceTable WHERE PlaceID = ?", (place_id,)).fetchone()
    return row[0] if row else f"(missing place {place_id})"


def link_text(conn, names, owner_type, owner_id, facts) -> str:
    if owner_type != OWNER_EVENT:
        return f"owner type {owner_type}, ID {owner_id}"
    event = conn.execute(
        "SELECT f.Name, e.OwnerType, e.OwnerID, e.Date, e.PlaceID, e.SiteID, e.Details FROM EventTable e"
        " LEFT JOIN FactTypeTable f ON f.FactTypeID = e.EventType WHERE e.EventID = ?", (owner_id,)).fetchone()
    if event is None:
        return f"E{owner_id} (missing event)"
    fact, ev_owner_type, ev_owner, date, place, site, details = event
    facts[fact] += 1
    if ev_owner_type == OWNER_PERSON:
        owner = f"P{ev_owner} {names.get(ev_owner, '')}"
    else:
        couple = conn.execute("SELECT FatherID, MotherID FROM FamilyTable WHERE FamilyID = ?", (ev_owner,)).fetchone()
        owner = f"F{ev_owner} {couple}"
    description = f" {details!r}" if details else ""
    return f"E{owner_id} {fact} {owner} {date} {place_name(conn, place)} / {place_name(conn, site)}{description}"


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    if len(sys.argv) < 3 or not sys.argv[2].isdigit():
        print(__doc__.strip().splitlines()[-1])
        return 2
    source_id = int(sys.argv[2])

    conn = connect_readonly(path)
    try:
        source = conn.execute("SELECT Name, TemplateID, Fields, ActualText, Comments FROM SourceTable"
                              " WHERE SourceID = ?", (source_id,)).fetchone()
        if source is None:
            print(f"No source S{source_id}")
            return 1
        names = person_names(conn)
        citations = conn.execute("SELECT CitationID, CitationName, Fields, ActualText, Comments FROM CitationTable"
                                 " WHERE SourceID = ? ORDER BY CitationID", (source_id,)).fetchall()
        facts = Counter()
        with output_file(f"source_{source_id}_inventory"):
            name, template, fields, text, comments = source
            print(f"S{source_id} {name}, template {template}")
            print(f"   fields: {read_fields(fields)}")
            print(f"   text: {text!r}")
            print(f"   comments: {comments!r}")
            for cid, cname, cfields, ctext, note in citations:
                print(f"\nC{cid} {cname!r}")
                print(f"   fields: {read_fields(cfields)}")
                print(f"   transcription: {ctext!r}")
                if note:
                    print(f"   note: {note!r}")
                for owner_type, owner_id, quality in conn.execute(
                        "SELECT OwnerType, OwnerID, Quality FROM CitationLinkTable WHERE CitationID = ?"
                        " ORDER BY LinkID", (cid,)):
                    print(f"   link {link_text(conn, names, owner_type, owner_id, facts)} [{quality}]")
                for media_id, media_path, media_file in conn.execute(
                        "SELECT m.MediaID, m.MediaPath, m.MediaFile FROM MediaLinkTable l"
                        " JOIN MultimediaTable m ON m.MediaID = l.MediaID WHERE l.OwnerType = ? AND l.OwnerID = ?"
                        " ORDER BY m.MediaID", (OWNER_CITATION, cid)):
                    print(f"   scan M{media_id} {media_path}\\{media_file}")
            print(f"\n{len(citations)} citations; event links by fact: {dict(sorted(facts.items()))}")
    finally:
        conn.close()
    print(f"S{source_id}: {len(citations)} citations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
