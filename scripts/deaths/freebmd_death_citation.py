"""Add a FreeBMD death index citation to a person's Death event.

Creates a citation under the FreeBMD death index source (default 589, already
on template 6; see freebmd_deaths.py) from a transcription in FreeBMD's layout
("Deaths <quarter> <year>", then the entry's columns separated by tabs). The
fields, CitationName and tidied transcription are built exactly as
freebmd_deaths.py builds them; AccessDate is the scan's last-modified date.
The citation is linked to the Death event --event with --quality (default
PIX). Attach the scan with scripts/media/attach_scan.py afterwards.

Dry run by default: prints what would change. --apply writes it in one
transaction. RootsMagic must be closed, and the file must be a working copy.

Usage: python freebmd_death_citation.py PATH_TO_RMTREE --event ID --text TEXT
           --scan WINDOWS_PATH [--source ID] [--quality XYZ] [--apply]
"""

import argparse
import sys

from freebmd_deaths import plan_citation
from rmutils import (
    connect_readonly,
    connect_readwrite,
    db_path_arg,
    fields_blob,
    utc_mod_date,
    windows_file_modified,
)

DEFAULT_SOURCE = 589
OWNER_PERSON, OWNER_EVENT = 0, 2
FACT_DEATH = 2


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="freebmd_death_citation.py PATH_TO_RMTREE")
    parser.add_argument("--event", type=int, required=True, help="the person's Death event")
    parser.add_argument("--text", required=True, help="transcription; \\t and \\n are read as tab and new line")
    parser.add_argument("--scan", required=True, help="Windows path of the scan (for the access date)")
    parser.add_argument("--source", type=int, default=DEFAULT_SOURCE)
    parser.add_argument("--quality", default="PIX")
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])
    text = args.text.replace("\\t", "\t").replace("\\n", "\n")

    conn = connect_readonly(path)
    try:
        event = conn.execute(
            "SELECT EventType, OwnerType, OwnerID FROM EventTable WHERE EventID = ?", (args.event,)
        ).fetchone()
        source = conn.execute(
            "SELECT TemplateID FROM SourceTable WHERE SourceID = ?", (args.source,)
        ).fetchone()
    finally:
        conn.close()
    if event is None or event[:2] != (FACT_DEATH, OWNER_PERSON):
        print(f"E{args.event} is not a person's Death event")
        return 1
    if source != (6,):
        print(f"Source S{args.source} is missing or not on template 6")
        return 1

    modified = windows_file_modified(args.scan)
    dates = {args.scan.lower(): modified} if modified else {}
    plan = plan_citation(0, event[2], "", text, [args.scan], dates)
    if plan.problem:
        print(f"Transcription not usable: {plan.problem}")
        return 1
    print(f"New citation under S{args.source} on Death event E{args.event} (P{event[2]}),"
          f" quality {args.quality}:")
    for key, value in plan.fields.items():
        print(f"   {key}: {value}")
    print(f"   ActualText: {plan.text!r}")
    for issue in plan.issues:
        print(f"   issue: {issue}")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    try:
        citation_id = conn.execute(
            "INSERT INTO CitationTable (SourceID, Comments, ActualText, RefNumber, Footnote,"
            " ShortFootnote, Bibliography, Fields, UTCModDate, CitationName)"
            " VALUES (?, '', ?, '', '', '', '', ?, ?, ?)",
            (args.source, plan.text, fields_blob(plan.fields, declaration=False), stamp, plan.name),
        ).lastrowid
        conn.execute(
            "INSERT INTO CitationLinkTable (CitationID, OwnerType, OwnerID, SortOrder, Quality,"
            " IsPrivate, Flags, UTCModDate) VALUES (?, ?, ?, 0, ?, 0, 0, ?)",
            (citation_id, OWNER_EVENT, args.event, args.quality, stamp),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"Applied: citation C{citation_id} on E{args.event}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
