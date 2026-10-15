"""Remove stray full stops after whole names in birth index entries.

In the citations of the given sources (default 583 and 590), the name in
SpecificItem ("entry for Ada Ellen. Wells, ...") loses a full stop that follows
a word of three or more letters ("Ellen." -> "Ellen"). Initials ("S.", "A.A.")
are kept. The citation name is rebuilt from the fields, and the same name is
corrected in the descriptions of scans attached to the citation. The
transcription (ActualText) is not changed.

Dry run by default: prints what would change. --apply writes it in one
transaction. RootsMagic must be closed, and the file must be a working copy.

Usage: python fix_name_stops.py PATH_TO_RMTREE [--source ID ...] [--apply]
"""

import argparse
import re
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
PREFIX = "entry for "
STRAY_STOP = re.compile(r"\b([A-Za-z]{3,})\.(?=\s|$)")
CITATION_FIELDS = ("AccessDate", "SpecificItem", "Citing")


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="fix_name_stops.py PATH_TO_RMTREE")
    parser.add_argument("--source", type=int, nargs="+", default=[583, 590])
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])

    marks = ",".join("?" * len(args.source))
    conn = connect_readonly(path)
    try:
        citations = conn.execute(
            f"SELECT CitationID, Fields FROM CitationTable WHERE SourceID IN ({marks}) ORDER BY CitationID",
            args.source,
        ).fetchall()
        media = conn.execute(
            "SELECT ml.OwnerID, m.MediaID, m.Description FROM MediaLinkTable ml"
            " JOIN MultimediaTable m USING (MediaID) WHERE ml.OwnerType = ?",
            (OWNER_CITATION,),
        ).fetchall()
    finally:
        conn.close()

    citation_changes, media_changes = [], {}
    for cid, blob in citations:
        fields = read_fields(blob)
        item = fields.get("SpecificItem", "")
        if not item.startswith(PREFIX):
            continue
        name = item[len(PREFIX):].split(",")[0]
        fixed = STRAY_STOP.sub(r"\1", name)
        if fixed == name:
            continue
        fields["SpecificItem"] = PREFIX + fixed + item[len(PREFIX) + len(name):]
        new_name = "; ".join(fields.get(f, "") for f in CITATION_FIELDS)
        citation_changes.append((cid, name, fixed, fields, new_name))
        for owner, mid, descr in media:
            if owner == cid and descr and f" {name}," in descr:
                media_changes[mid] = media_changes.get(mid, descr).replace(f" {name},", f" {fixed},")

    for cid, name, fixed, _, _ in citation_changes:
        print(f"C{cid}: '{name}' -> '{fixed}'")
    for mid in media_changes:
        print(f"M{mid}: description corrected")
    print(f"{len(citation_changes)} citations; {len(media_changes)} scan descriptions")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    try:
        for cid, _, _, fields, new_name in citation_changes:
            conn.execute(
                "UPDATE CitationTable SET Fields = ?, CitationName = ?, UTCModDate = ? WHERE CitationID = ?",
                (fields_blob(fields, declaration=False), new_name, stamp, cid),
            )
        for mid, descr in media_changes.items():
            conn.execute(
                "UPDATE MultimediaTable SET Description = ?, UTCModDate = ? WHERE MediaID = ?",
                (descr, stamp, mid),
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
