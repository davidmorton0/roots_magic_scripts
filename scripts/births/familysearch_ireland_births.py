"""Convert the FamilySearch Irish birth index source (S584) like the FreeBMD one.

S584 "Birth Register - Ireland - FamilySearch" moves from the US birth
certificate template to template 6 (Complex Website), with FamilySearch as the
website, and its two citations get template-6 fields. The values were read
from each citation's transcription (ActualText), which holds FamilySearch's own
citation with the access date:
  C2663 Joseph Gracey  Lurgan, vol. 1, p. 667, Jan-Mar 1891, accessed 8 July 2012
  C3334 James Gracey   Lurgan, vol. 1, p. 729, Apr-Jun 1895, accessed 10 March 2018
The transcriptions are not changed.

Dry run by default. --apply writes it in one transaction. RootsMagic must be
closed, and the file must be a working copy.

Usage: python familysearch_ireland_births.py PATH_TO_RMTREE [--apply]
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

SOURCE = 584
TEMPLATE_ID = 6
SOURCE_FIELDS = {
    "DatabaseCreator": "",
    "DatabaseTitle": "Ireland Civil Registration Indexes, 1845-1958",
    "Descriptor": "database",
    "WebsiteCreator": "",
    "WebsiteTitle": "FamilySearch",
    "URL": "https://www.familysearch.org",
}
CITING = "General Registry, Custom House, Dublin, Births registered in {} {}"
CITATIONS = {
    2663: {
        "AccessDate": "8 July 2012",
        "SpecificItem": "entry for Joseph Gracey, Lurgan, vol. 1, p. 667",
        "Citing": CITING.format("January, February, and March", 1891),
    },
    3334: {
        "AccessDate": "10 March 2018",
        "SpecificItem": "entry for James Gracey, Lurgan, vol. 1, p. 729",
        "Citing": CITING.format("April, May, and June", 1895),
    },
}
CITATION_FIELDS = ("AccessDate", "SpecificItem", "Citing")
OLD_NAMES = {2663: "Joseph Gracey", 3334: "James Gracey"}


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="familysearch_ireland_births.py PATH_TO_RMTREE")
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])

    conn = connect_readonly(path)
    try:
        source = conn.execute(
            "SELECT TemplateID FROM SourceTable WHERE SourceID = ?", (SOURCE,)
        ).fetchone()
        rows = {
            cid: (sid, read_fields(blob))
            for cid, sid, blob in conn.execute(
                "SELECT CitationID, SourceID, Fields FROM CitationTable WHERE CitationID IN (?, ?)",
                tuple(CITATIONS),
            )
        }
    finally:
        conn.close()

    problems = []
    if source is None:
        problems.append(f"source S{SOURCE} not found")
    elif source[0] == TEMPLATE_ID:
        problems.append(f"S{SOURCE} is already on template {TEMPLATE_ID}")
    for cid, name in OLD_NAMES.items():
        sid, fields = rows.get(cid, (None, {}))
        if sid != SOURCE or fields.get("Name") != name:
            problems.append(f"C{cid} is not {name}'s citation under S{SOURCE}")
    if problems:
        print("Not possible: " + "; ".join(problems))
        return 1

    print(f"S{SOURCE}: template {source[0]} -> {TEMPLATE_ID}")
    for key, value in SOURCE_FIELDS.items():
        print(f"   {key}: {value!r}")
    for cid, fields in CITATIONS.items():
        print(f"C{cid}:")
        for key, value in fields.items():
            print(f"   {key}: {value}")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    try:
        conn.execute(
            "UPDATE SourceTable SET TemplateID = ?, Fields = ?, UTCModDate = ? WHERE SourceID = ?",
            (TEMPLATE_ID, fields_blob(SOURCE_FIELDS, declaration=False), stamp, SOURCE),
        )
        for cid, fields in CITATIONS.items():
            conn.execute(
                "UPDATE CitationTable SET Fields = ?, CitationName = ?, UTCModDate = ? WHERE CitationID = ?",
                (fields_blob(fields, declaration=False),
                 "; ".join(fields[f] for f in CITATION_FIELDS), stamp, cid),
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
