"""Add a GRO online index citation to a person's Birth event.

Creates the source "Birth Register - UK - GRO" (template 6, Complex Website)
the first time, then adds a citation to it:
  AccessDate    --accessed (as written, e.g. "15 October 2026")
  SpecificItem  "entry for NAME, DISTRICT, vol. VOL, p. PAGE, mother's maiden name MMN"
  Citing        "General Register Office, Births registered in <quarter months> YEAR"
  ActualText    --text (the result line as shown by the GRO)
  Quality       PIX (primary information, indirect evidence, derivative source)
and links it to the Birth event --event.

Dry run by default: prints what would change. --apply writes it in one
transaction. RootsMagic must be closed, and the file must be a working copy.

Usage: python gro_index_citation.py PATH_TO_RMTREE --event ID --name NAME
           --district D --volume V --page P --mmn SURNAME --year YYYY --quarter 1-4
           --accessed DATE --text TEXT [--apply]
"""

import argparse
import sys

from rmutils import (
    connect_readonly,
    connect_readwrite,
    db_path_arg,
    fields_blob,
    utc_mod_date,
)

SOURCE_NAME = "Birth Register - UK - GRO"
TEMPLATE_ID = 6
SOURCE_FIELDS = {
    "DatabaseCreator": "",
    "DatabaseTitle": "GRO Online Index: Births",
    "Descriptor": "database",
    "WebsiteCreator": "",
    "WebsiteTitle": "General Register Office",
    "URL": "https://www.gro.gov.uk",
}
CITATION_FIELDS = ("AccessDate", "SpecificItem", "Citing")
QUARTER_MONTHS = {
    1: "January, February, and March",
    2: "April, May, and June",
    3: "July, August, and September",
    4: "October, November, and December",
}
OWNER_PERSON, OWNER_EVENT = 0, 2
FACT_BIRTH = 1
QUALITY = "PIX"


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="gro_index_citation.py PATH_TO_RMTREE")
    for name in ("name", "district", "volume", "page", "mmn", "accessed", "text"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--event", type=int, required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--quarter", type=int, choices=[1, 2, 3, 4], required=True)
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])

    conn = connect_readonly(path)
    try:
        event = conn.execute(
            "SELECT EventType, OwnerType FROM EventTable WHERE EventID = ?", (args.event,)
        ).fetchone()
        source = conn.execute(
            "SELECT SourceID FROM SourceTable WHERE Name = ?", (SOURCE_NAME,)
        ).fetchone()
    finally:
        conn.close()
    if event != (FACT_BIRTH, OWNER_PERSON):
        print(f"E{args.event} is not a person's Birth event")
        return 1

    fields = {
        "AccessDate": args.accessed,
        "SpecificItem": f"entry for {args.name}, {args.district}, vol. {args.volume},"
                        f" p. {args.page}, mother's maiden name {args.mmn}",
        "Citing": f"General Register Office, Births registered in"
                  f" {QUARTER_MONTHS[args.quarter]} {args.year}",
    }
    citation_name = "; ".join(fields[f] for f in CITATION_FIELDS)
    if source:
        print(f"Source S{source[0]} '{SOURCE_NAME}' exists")
    else:
        print(f"New source '{SOURCE_NAME}' (template {TEMPLATE_ID})")
        for key, value in SOURCE_FIELDS.items():
            print(f"   {key}: {value!r}")
    print(f"New citation on Birth event E{args.event}, quality {QUALITY}:")
    for key, value in fields.items():
        print(f"   {key}: {value}")
    print(f"   ActualText: {args.text!r}")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    try:
        source_id = source[0] if source else conn.execute(
            "INSERT INTO SourceTable (Name, RefNumber, ActualText, Comments, IsPrivate,"
            " TemplateID, Fields, UTCModDate) VALUES (?, '', '', '', 0, ?, ?, ?)",
            (SOURCE_NAME, TEMPLATE_ID, fields_blob(SOURCE_FIELDS, declaration=False), stamp),
        ).lastrowid
        citation_id = conn.execute(
            "INSERT INTO CitationTable (SourceID, Comments, ActualText, RefNumber, Footnote,"
            " ShortFootnote, Bibliography, Fields, UTCModDate, CitationName)"
            " VALUES (?, '', ?, '', '', '', '', ?, ?, ?)",
            (source_id, args.text, fields_blob(fields, declaration=False), stamp, citation_name),
        ).lastrowid
        conn.execute(
            "INSERT INTO CitationLinkTable (CitationID, OwnerType, OwnerID, Quality,"
            " IsPrivate, Flags, UTCModDate) VALUES (?, ?, ?, ?, 0, 0, ?)",
            (citation_id, OWNER_EVENT, args.event, QUALITY, stamp),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"Applied: citation C{citation_id} under S{source_id}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
