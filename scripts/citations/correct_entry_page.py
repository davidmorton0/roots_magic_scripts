"""Correct the page number of an index entry in a citation and its scans.

Replaces "p. OLD" with "p. NEW" in the citation's SpecificItem, rebuilds the
citation name, sets the citation note to --note, and corrects the page in the
reference number ("... OLD" at the end) and description ("p. OLD") of scans
attached to the citation. The transcription (ActualText) is not changed: it
stays as received.

Dry run by default: prints what would change. --apply writes it in one
transaction. RootsMagic must be closed, and the file must be a working copy.

Usage: python correct_entry_page.py PATH_TO_RMTREE --citation ID --old PAGE --new PAGE
           --note TEXT [--apply]
"""

import argparse
import sys

from rmutils import (
    connect_readonly,
    connect_readwrite,
    db_path_arg,
    fields_blob,
    read_fields,
    utc_mod_date,
)

OWNER_CITATION = 4
CITATION_FIELDS = ("AccessDate", "SpecificItem", "Citing")


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="correct_entry_page.py PATH_TO_RMTREE")
    parser.add_argument("--citation", type=int, required=True)
    parser.add_argument("--old", required=True)
    parser.add_argument("--new", required=True)
    parser.add_argument("--note", required=True)
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])
    old_p, new_p = f"p. {args.old}", f"p. {args.new}"

    conn = connect_readonly(path)
    try:
        row = conn.execute(
            "SELECT Fields, Comments FROM CitationTable WHERE CitationID = ?", (args.citation,)
        ).fetchone()
        media = conn.execute(
            "SELECT m.MediaID, m.RefNumber, m.Description FROM MediaLinkTable ml"
            " JOIN MultimediaTable m USING (MediaID) WHERE ml.OwnerType = ? AND ml.OwnerID = ?",
            (OWNER_CITATION, args.citation),
        ).fetchall()
    finally:
        conn.close()
    if row is None:
        print(f"Citation C{args.citation} not found")
        return 1
    fields = read_fields(row[0])
    if old_p not in fields.get("SpecificItem", ""):
        print(f"C{args.citation} SpecificItem has no '{old_p}'")
        return 1
    fields["SpecificItem"] = fields["SpecificItem"].replace(old_p, new_p)
    name = "; ".join(fields.get(f, "") for f in CITATION_FIELDS)

    media_changes = []
    for mid, ref, descr in media:
        new_ref = ref[: -len(args.old)] + args.new if ref and ref.endswith(f" {args.old}") else ref
        new_descr = (descr or "").replace(old_p, new_p)
        if (new_ref, new_descr) != (ref, descr or ""):
            media_changes.append((mid, ref, new_ref, new_descr))

    print(f"C{args.citation}: SpecificItem -> {fields['SpecificItem']}")
    print(f"   note: '{row[1] or ''}' -> '{args.note}'")
    for mid, ref, new_ref, _ in media_changes:
        print(f"M{mid}: reference '{ref}' -> '{new_ref}'; description page corrected")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    try:
        conn.execute(
            "UPDATE CitationTable SET Fields = ?, CitationName = ?, Comments = ?, UTCModDate = ?"
            " WHERE CitationID = ?",
            (fields_blob(fields, declaration=False), name, args.note, stamp, args.citation),
        )
        for mid, _, new_ref, new_descr in media_changes:
            conn.execute(
                "UPDATE MultimediaTable SET RefNumber = ?, Description = ?, UTCModDate = ? WHERE MediaID = ?",
                (new_ref, new_descr, stamp, mid),
            )
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
