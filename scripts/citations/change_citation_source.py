"""Move a citation to another source, replacing its entry text and transcription.

Sets the citation's SourceID to --to-source, its SpecificItem to
--specific-item (other fields kept) and its transcription (ActualText) to
--text, and rebuilds the citation name. Optionally sets the description of a
scan attached to the citation (--media ID --description TEXT).
Both sources must use the same template, so the citation's fields still fit.

Dry run by default: prints old and new values. --apply writes them in one
transaction. RootsMagic must be closed, and the file must be a working copy.

Usage: python change_citation_source.py PATH_TO_RMTREE --citation ID --to-source ID
           --specific-item TEXT --text TEXT [--media ID --description TEXT] [--apply]
"""

import argparse
import sys

from rmutils import (
    connect_readonly,
    connect_readwrite,
    db_path_arg,
    fields_blob,
    read_fields,
    template_fields,
    utc_mod_date,
)

OWNER_CITATION = 4


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="change_citation_source.py PATH_TO_RMTREE")
    parser.add_argument("--citation", type=int, required=True)
    parser.add_argument("--to-source", type=int, required=True)
    parser.add_argument("--specific-item", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--media", type=int)
    parser.add_argument("--description")
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])
    if (args.media is None) != (args.description is None):
        print("--media and --description go together")
        return 1

    conn = connect_readonly(path)
    try:
        row = conn.execute(
            """SELECT c.SourceID, c.Fields, c.ActualText, s.TemplateID FROM CitationTable c
               JOIN SourceTable s USING (SourceID) WHERE c.CitationID = ?""",
            (args.citation,),
        ).fetchone()
        target = conn.execute(
            "SELECT Name, TemplateID FROM SourceTable WHERE SourceID = ?", (args.to_source,)
        ).fetchone()
        media = None
        if args.media is not None:
            media = conn.execute(
                "SELECT m.Description FROM MultimediaTable m JOIN MediaLinkTable ml USING (MediaID)"
                " WHERE m.MediaID = ? AND ml.OwnerType = ? AND ml.OwnerID = ?",
                (args.media, OWNER_CITATION, args.citation),
            ).fetchone()
        order = [n for n, is_cit in template_fields(conn, row[3]) if is_cit] if row else []
    finally:
        conn.close()
    if row is None or target is None:
        print(f"Citation C{args.citation} or source S{args.to_source} not found")
        return 1
    if target[1] != row[3]:
        print(f"S{args.to_source} uses template {target[1]}, not {row[3]}")
        return 1
    if args.media is not None and media is None:
        print(f"M{args.media} is not attached to C{args.citation}")
        return 1

    fields = read_fields(row[1])
    old_item = fields.get("SpecificItem", "")
    fields["SpecificItem"] = args.specific_item
    name = "; ".join(fields.get(n, "") for n in order)

    print(f"C{args.citation}: source S{row[0]} -> S{args.to_source} '{target[0]}'")
    print(f"   SpecificItem: '{old_item}' -> '{args.specific_item}'")
    print("   transcription now:")
    for line in (row[2] or "").splitlines():
        print(f"      {line}")
    print("   transcription new:")
    for line in args.text.splitlines():
        print(f"      {line}")
    if media is not None:
        print(f"M{args.media} description: '{media[0]}' -> '{args.description}'")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    try:
        conn.execute(
            "UPDATE CitationTable SET SourceID = ?, Fields = ?, CitationName = ?, ActualText = ?,"
            " UTCModDate = ? WHERE CitationID = ?",
            (args.to_source, fields_blob(fields, declaration=False), name, args.text, stamp, args.citation),
        )
        if media is not None:
            conn.execute("UPDATE MultimediaTable SET Description = ?, UTCModDate = ? WHERE MediaID = ?",
                         (args.description, stamp, args.media))
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
