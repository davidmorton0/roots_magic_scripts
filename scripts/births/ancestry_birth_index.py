"""Convert the Ancestry birth index source (S590) like the FreeBMD one.

S590 "Birth Register - UK - Ancestry" holds one source for both Ancestry birth
index databases (user's choice); the database is named in each citation.
Changes, all in one transaction:
  - S590 moves to template 6 (Complex Website) with Ancestry as the website.
  - C4471 (William A Morton, Ancestry transcription) moves from S583 to S590;
    the database name is added to its SpecificItem.
  - C4522 (Ethel Williams) gets template-6 fields, a transcription read from
    her scan, and an access date from the scan's last-modified date.
  - C4523, a second citation of the same entry on the same Birth event and
    scan, is deleted with its citation link and media link.
Entries were read from the scans on 2026-10-15:
  WIL-E-BRG-1904-Q1.jpg  Ethel, Basford 7b 273, Jan-Mar 1904, printed page 622
  MOR-WA-BRG-1934-Q4.jpg William A., mother Blythe, Basford 7b 252,
                         Oct-Dec 1934, printed page 122

Dry run by default. --apply writes it. RootsMagic must be closed, and the file
must be a working copy.

Usage: python ancestry_birth_index.py PATH_TO_RMTREE [--apply]
"""

import argparse
import sys

from rmutils import (
    access_date_text,
    connect_readonly,
    connect_readwrite,
    db_path_arg,
    fields_blob,
    read_fields,
    utc_mod_date,
    windows_file_modified,
)

SOURCE = 583
ANCESTRY = 590
TEMPLATE_ID = 6
OWNER_CITATION = 4
DB_1837 = "England & Wales, Civil Registration Birth Index, 1837-1915"
DB_1916 = "England & Wales, Civil Registration Birth Index, 1916-2007"
SOURCE_FIELDS = {
    "DatabaseCreator": "",
    "DatabaseTitle": "England & Wales, Civil Registration Birth Index",
    "Descriptor": "database",
    "WebsiteCreator": "Ancestry.com Operations Inc.",
    "WebsiteTitle": "Ancestry",
    "URL": "https://www.ancestry.co.uk",
}
CITATION_FIELDS = ("AccessDate", "SpecificItem", "Citing")
WILLIAM, ETHEL, ETHEL_DUPLICATE = 4471, 4522, 4523
ETHEL_SCAN = "H:\\My Drive\\Records\\Births\\Britain\\Registers\\WIL-E-BRG-1904-Q1.jpg"
ETHEL_TEXT = "Births Mar 1904\nWilliams\tEthel\tBasford\t7b\t273\n(read from the scan; printed index page 622)"
ETHEL_ITEM = f"entry for Ethel Williams, Basford, vol. 7b, p. 273 ({DB_1837})"
ETHEL_CITING = "General Register Office, Births registered in January, February, and March 1904"


def citation_name(fields: dict[str, str]) -> str:
    return "; ".join(fields[name] for name in CITATION_FIELDS)


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="ancestry_birth_index.py PATH_TO_RMTREE")
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])

    conn = connect_readonly(path)
    try:
        source = conn.execute(
            "SELECT TemplateID FROM SourceTable WHERE SourceID = ?", (ANCESTRY,)
        ).fetchone()
        rows = {
            cid: (sid, read_fields(blob))
            for cid, sid, blob in conn.execute(
                "SELECT CitationID, SourceID, Fields FROM CitationTable WHERE CitationID IN (?, ?, ?)",
                (WILLIAM, ETHEL, ETHEL_DUPLICATE),
            )
        }
        duplicate_links = conn.execute(
            "SELECT LinkID, OwnerType, OwnerID FROM CitationLinkTable WHERE CitationID = ?",
            (ETHEL_DUPLICATE,),
        ).fetchall()
        ethel_links = conn.execute(
            "SELECT OwnerType, OwnerID FROM CitationLinkTable WHERE CitationID = ?", (ETHEL,)
        ).fetchall()
        duplicate_media = conn.execute(
            "SELECT LinkID, MediaID FROM MediaLinkTable WHERE OwnerType = ? AND OwnerID = ?",
            (OWNER_CITATION, ETHEL_DUPLICATE),
        ).fetchall()
    finally:
        conn.close()

    problems = []
    if source is None:
        problems.append(f"source S{ANCESTRY} not found")
    if rows.get(WILLIAM, (None,))[0] != SOURCE:
        problems.append(f"C{WILLIAM} is not under S{SOURCE}")
    if rows.get(ETHEL, (None,))[0] != ANCESTRY or rows.get(ETHEL_DUPLICATE, (None,))[0] != ANCESTRY:
        problems.append(f"C{ETHEL}/C{ETHEL_DUPLICATE} are not under S{ANCESTRY}")
    if sorted((t, o) for _, t, o in duplicate_links) != sorted(ethel_links):
        problems.append(f"C{ETHEL_DUPLICATE} is not linked to the same records as C{ETHEL}")
    if problems:
        print("Not possible: " + "; ".join(problems))
        return 1

    modified = windows_file_modified(ETHEL_SCAN)
    william = dict(rows[WILLIAM][1])
    william["SpecificItem"] += f" ({DB_1916})"
    ethel = {
        "AccessDate": access_date_text(modified) if modified else "",
        "SpecificItem": ETHEL_ITEM,
        "Citing": ETHEL_CITING,
    }

    print(f"S{ANCESTRY}: template {source[0]} -> {TEMPLATE_ID}")
    for key, value in SOURCE_FIELDS.items():
        print(f"   {key}: {value!r}")
    print(f"C{WILLIAM}: S{SOURCE} -> S{ANCESTRY}; SpecificItem -> {william['SpecificItem']}")
    print(f"C{ETHEL}:")
    for key, value in ethel.items():
        print(f"   {key}: {value}")
    print(f"   ActualText: {ETHEL_TEXT!r}")
    print(f"C{ETHEL_DUPLICATE}: delete, with citation links {[l for l, _, _ in duplicate_links]}"
          f" and media links {[l for l, _ in duplicate_media]} (the scan stays, on C{ETHEL})")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    try:
        conn.execute(
            "UPDATE SourceTable SET TemplateID = ?, Fields = ?, UTCModDate = ? WHERE SourceID = ?",
            (TEMPLATE_ID, fields_blob(SOURCE_FIELDS, declaration=False), stamp, ANCESTRY),
        )
        conn.execute(
            "UPDATE CitationTable SET SourceID = ?, Fields = ?, CitationName = ?, UTCModDate = ?"
            " WHERE CitationID = ?",
            (ANCESTRY, fields_blob(william, declaration=False), citation_name(william), stamp, WILLIAM),
        )
        conn.execute(
            "UPDATE CitationTable SET Fields = ?, CitationName = ?, ActualText = ?, UTCModDate = ?"
            " WHERE CitationID = ?",
            (fields_blob(ethel, declaration=False), citation_name(ethel), ETHEL_TEXT, stamp, ETHEL),
        )
        conn.execute("DELETE FROM MediaLinkTable WHERE OwnerType = ? AND OwnerID = ?",
                     (OWNER_CITATION, ETHEL_DUPLICATE))
        conn.execute("DELETE FROM CitationLinkTable WHERE CitationID = ?", (ETHEL_DUPLICATE,))
        conn.execute("DELETE FROM CitationTable WHERE CitationID = ?", (ETHEL_DUPLICATE,))
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
