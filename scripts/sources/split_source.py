"""Move some citations of a source into another source, new or existing.

Moves the old source's citations whose transcription (ActualText) contains
--match into either:
  --to SOURCE_ID   an existing source (it must use the same template, so the
                   citations' fields still fit), or
  --name NEW_NAME  a new source, created as a copy of the old one (same
                   template, fields and text) with any field values given with
                   --field and, optionally, new --comments.
The citations themselves are not changed.

Dry run by default: prints what would change. --apply writes it in one
transaction. RootsMagic must be closed, and the file must be a working copy.

Usage: python split_source.py PATH_TO_RMTREE --from SOURCE_ID --match TEXT
           [--include CITATION_ID ...] (--to SOURCE_ID | --name NEW_NAME [--field NAME=VALUE ...] [--comments TEXT])
           [--apply]
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

SOURCE_COLUMNS = "Name, RefNumber, ActualText, Comments, IsPrivate, TemplateID, Fields"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="split_source.py PATH_TO_RMTREE")
    parser.add_argument("--from", dest="source", type=int, required=True)
    parser.add_argument("--match", required=True, help="text the transcription must contain")
    parser.add_argument("--include", type=int, nargs="*", default=[],
                        help="citation IDs to move as well, whatever their transcription")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--to", type=int, help="existing source to move them into")
    target.add_argument("--name", help="name of a new source to create")
    parser.add_argument("--field", action="append", default=[], help="NAME=VALUE (new source)")
    parser.add_argument("--comments", help="new source's comments (default: copied)")
    parser.add_argument("--apply", action="store_true", help="write the changes")
    return parser.parse_args(argv)


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    args = parse_args(sys.argv[2:])

    conn = connect_readonly(path)
    try:
        source = conn.execute(
            f"SELECT {SOURCE_COLUMNS} FROM SourceTable WHERE SourceID = ?", (args.source,)
        ).fetchone()
        if source is None:
            print(f"Source S{args.source} not found")
            return 1
        target = None
        if args.to is not None:
            target = conn.execute(
                "SELECT Name, TemplateID FROM SourceTable WHERE SourceID = ?", (args.to,)
            ).fetchone()
            if target is None:
                print(f"Source S{args.to} not found")
                return 1
            if target[1] != source[5]:
                print(f"S{args.to} uses template {target[1]}, not {source[5]}: citation fields would not fit")
                return 1
        elif conn.execute(
            "SELECT 1 FROM SourceTable WHERE Name = ? COLLATE NOCASE", (args.name,)
        ).fetchone():
            print(f"A source named '{args.name}' already exists")
            return 1
        citations = [
            (cid, cname)
            for cid, cname, text in conn.execute(
                "SELECT CitationID, CitationName, ActualText FROM CitationTable"
                " WHERE SourceID = ? ORDER BY CitationID",
                (args.source,),
            )
            if args.match in (text or "") or cid in args.include
        ]
        missing = set(args.include) - {cid for cid, _ in citations}
        if missing:
            print(f"Not citations of S{args.source}: {sorted(missing)}")
            return 1
    finally:
        conn.close()

    old_name, ref, text, comments, private, template, blob = source
    fields = read_fields(blob)
    if target:
        print(f"Move into existing source S{args.to} '{target[0]}' (template {target[1]})")
    else:
        for item in args.field:
            name, sep, value = item.partition("=")
            if not sep or name not in fields:
                print(f"--field {item!r}: field must be one of {list(fields)}")
                return 1
            fields[name] = value
        print(f"New source '{args.name}' (copy of S{args.source} '{old_name}', template {template})")
        for name, value in fields.items():
            print(f"   {name}: {value!r}")
        print(f"   Comments: {'copied' if args.comments is None else repr(args.comments)}")
    print(f"Citations to move from S{args.source}: {len(citations)}")
    for cid, cname in citations:
        print(f"   C{cid} {cname}")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    try:
        if target:
            new_id = args.to
        else:
            new_id = conn.execute(
                f"INSERT INTO SourceTable ({SOURCE_COLUMNS}, UTCModDate)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (args.name, ref, text, comments if args.comments is None else args.comments,
                 private, template, fields_blob(fields, declaration=False), stamp),
            ).lastrowid
        for cid, _ in citations:
            cur = conn.execute(
                "UPDATE CitationTable SET SourceID = ?, UTCModDate = ?"
                " WHERE CitationID = ? AND SourceID = ?",
                (new_id, stamp, cid, args.source),
            )
            if cur.rowcount != 1:
                raise RuntimeError(f"citation C{cid} not moved")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"Applied: {len(citations)} citations moved to S{new_id}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
