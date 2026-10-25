"""Add a citation to an existing source and link it to facts.

The citation fields are those of the source's template (template 6, Complex Website: AccessDate,
SpecificItem, Citing); a free-form source (template 0) takes Page. CitationName is the citation
field values joined with "; " in template order (the Page text for free-form), as RootsMagic 12
stores them. Fields are written without a declaration, as RootsMagic 12 saves citation rows.
Refused when a field is not a citation field of the template, a link target is missing, a quality
is not three characters, or a citation of the source already has the same CitationName.

Links: --link event:ID:QUALITY (CitationLinkTable owner type 2), family:ID:QUALITY (1),
name:ID:QUALITY (7), as many as needed.

Dry run by default: prints what would change. --apply writes it in one transaction.
RootsMagic must be closed, and the file must be a working copy.

Usage: python add_citation.py PATH_TO_RMTREE --source ID --field NAME=VALUE [--field ...]
           [--text-file FILE] [--comments TEXT] [--link KIND:ID:QUALITY ...] [--apply]
"""

import argparse
import sys
from pathlib import Path

from rmutils import connect_readonly, connect_readwrite, db_path_arg, fields_blob, template_fields, utc_mod_date

OWNER_TYPES = {"family": (1, "FamilyTable", "FamilyID"), "event": (2, "EventTable", "EventID"),
               "name": (7, "NameTable", "NameID")}


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="add_citation.py PATH_TO_RMTREE")
    parser.add_argument("--source", type=int, required=True)
    parser.add_argument("--field", action="append", default=[], required=True)
    parser.add_argument("--text-file")
    parser.add_argument("--comments", default="")
    parser.add_argument("--link", action="append", default=[])
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])

    text = Path(args.text_file).read_text(encoding="utf-8").replace("\r\n", "\n").strip().replace("\n", "\r\n") \
        if args.text_file else ""
    problems = []
    fields = {}
    for item in args.field:
        name, sep, value = item.partition("=")
        if not sep:
            problems.append(f"--field {item!r} is not NAME=VALUE")
        fields[name] = value
    links = []
    for item in args.link:
        parts = item.split(":")
        if len(parts) != 3 or parts[0] not in OWNER_TYPES or not parts[1].isdigit():
            problems.append(f"--link {item!r} is not KIND:ID:QUALITY (kind event, family or name)")
            continue
        if len(parts[2]) != 3:
            problems.append(f"quality {parts[2]!r} is not three characters")
        links.append((parts[0], int(parts[1]), parts[2]))

    conn = connect_readonly(path)
    try:
        source = conn.execute("SELECT Name, TemplateID FROM SourceTable WHERE SourceID = ?", (args.source,)).fetchone()
        if source is None:
            print(f"S{args.source} not found")
            return 1
        names = [n for n, is_citation in template_fields(conn, source[1]) if is_citation] if source[1] else ["Page"]
        problems += [f"{n!r} is not a citation field of template {source[1]} ({', '.join(names)})"
                     for n in fields if n not in names]
        citation_name = "; ".join(fields[n] for n in names if fields.get(n))
        for kind, owner, _ in links:
            _, table, key = OWNER_TYPES[kind]
            if not conn.execute(f"SELECT 1 FROM {table} WHERE {key} = ?", (owner,)).fetchone():
                problems.append(f"{kind} {owner} not found")
        same = conn.execute("SELECT CitationID FROM CitationTable WHERE SourceID = ? AND CitationName = ?",
                            (args.source, citation_name)).fetchone()
        if same:
            problems.append(f"C{same[0]} of S{args.source} already has this CitationName")
    finally:
        conn.close()

    print(f"New citation under S{args.source} '{source[0]}':")
    for n in names:
        if n in fields:
            print(f"   {n}: {fields[n]}")
    print(f"   CitationName: {citation_name}")
    print(f"   ActualText: {text!r}")
    if args.comments:
        print(f"   Comments: {args.comments!r}")
    for kind, owner, quality in links:
        print(f"   link -> {kind} {owner} {quality}")
    if problems:
        print("Refused:\n   " + "\n   ".join(problems))
        return 1
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    try:
        with conn:
            cid = conn.execute(
                "INSERT INTO CitationTable (SourceID, Comments, ActualText, RefNumber, Footnote, ShortFootnote,"
                " Bibliography, Fields, UTCModDate, CitationName) VALUES (?, ?, ?, '', '', '', '', ?, ?, ?)",
                (args.source, args.comments, text, fields_blob({n: fields[n] for n in names if n in fields},
                                                                declaration=False), stamp, citation_name)).lastrowid
            for kind, owner, quality in links:
                conn.execute("INSERT INTO CitationLinkTable (CitationID, OwnerType, OwnerID, SortOrder, Quality,"
                             " IsPrivate, Flags, UTCModDate) VALUES (?, ?, ?, 0, ?, 0, 0, ?)",
                             (cid, OWNER_TYPES[kind][0], owner, quality, stamp))
    finally:
        conn.close()
    print(f"Applied: citation C{cid}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
