"""Get, create, edit or delete citations (CitationTable).

  get     ID [ID ...] | --source ID   Print citations with their fields, links and scans (read-only).
  create  --source ID --field NAME=VALUE ... [--set COLUMN=VALUE ...] [--text-file FILE]
          [--link KIND:ID:QUALITY ...]
  edit    ID [--field NAME=VALUE ...] [--set COLUMN=VALUE ...] [--text-file FILE]
  delete  ID [--with-links]

--field sets a citation field of the source's template (Page for a free-form source); CitationName is
rebuilt as the field values joined with "; " in template order, and Fields is written without a
declaration, as RootsMagic 12 saves citation rows. --set sets Comments, RefNumber, Footnote,
ShortFootnote or Bibliography. --text-file sets ActualText (line ends become CR LF). --link kinds:
person, family, event, name (owner types 0, 1, 2, 7).

Refused when a field is not a citation field of the template, a link target is missing, a quality is
not three characters, another citation of the source has the same CitationName, or (delete) the
citation still has scans, or has links and --with-links is not given. The source of a citation is not
changed here (a source's citations move with sources/split_source.py).

create, edit and delete are dry runs by default: they print what would change. --apply writes it in
one transaction. RootsMagic must be closed, and the file must be a working copy.

Usage: python citation.py PATH_TO_RMTREE get|create|edit|delete ... [--apply]
"""

import argparse
import sys
from pathlib import Path

from rmutils import (
    OWNER_TYPES,
    connect_readonly,
    db_path_arg,
    fields_blob,
    parse_assignments,
    read_fields,
    template_fields,
    utc_mod_date,
    write_changes,
)

OWNER_OF_CODE = {0: "person", 1: "family", 2: "event", 3: "source", 7: "name"}
OWNER_MEDIA_CITATION = 4
SET_COLUMNS = ("Comments", "RefNumber", "Footnote", "ShortFootnote", "Bibliography")


def citation_field_names(conn, source_id: int) -> list[str]:
    """Citation fields of the source's template, in order; Page for a free-form source."""
    template = conn.execute("SELECT TemplateID FROM SourceTable WHERE SourceID = ?", (source_id,)).fetchone()[0]
    return [n for n, is_citation in template_fields(conn, template) if is_citation] if template else ["Page"]


def citation_name(names: list[str], fields: dict[str, str]) -> str:
    """Every citation field in template order, an empty one as an empty part (as in 19 of the 20 template 6
    citations with an empty field, 2026-10-28)."""
    return "; ".join(fields.get(n, "") for n in names)


def read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8").replace("\r\n", "\n").strip().replace("\n", "\r\n")


def check_sets(sets: dict[str, str], problems: list[str]) -> None:
    for column in [c for c in sets if c not in SET_COLUMNS]:
        problems.append(f"--set {column!r} is not one of {', '.join(SET_COLUMNS)}")
        del sets[column]


def get(path: Path, args) -> int:
    conn = connect_readonly(path)
    try:
        ids = args.ids or [r[0] for r in conn.execute(
            "SELECT CitationID FROM CitationTable WHERE SourceID = ? ORDER BY CitationID", (args.source,))]
        if not ids:
            print("No citations found")
            return 1
        for cid in ids:
            row = conn.execute(
                "SELECT c.SourceID, s.Name, c.CitationName, c.Comments, c.ActualText, c.RefNumber, c.Footnote,"
                " c.ShortFootnote, c.Bibliography, c.Fields, c.UTCModDate FROM CitationTable c"
                " LEFT JOIN SourceTable s USING (SourceID) WHERE c.CitationID = ?", (cid,)).fetchone()
            if row is None:
                print(f"C{cid} not found")
                return 1
            source, source_name, name, comments, text, ref, foot, short, bib, blob, stamp = row
            print(f"C{cid}  S{source} '{source_name}'")
            print(f"   CitationName: {name}")
            for field, value in read_fields(blob).items():
                print(f"   field {field}: {value}")
            for label, value in (("Comments", comments), ("RefNumber", ref), ("Footnote", foot),
                                 ("ShortFootnote", short), ("Bibliography", bib), ("ActualText", text)):
                if value:
                    print(f"   {label}: {value!r}")
            print(f"   UTCModDate: {stamp}")
            for owner_type, owner, quality in conn.execute(
                    "SELECT OwnerType, OwnerID, Quality FROM CitationLinkTable WHERE CitationID = ?"
                    " ORDER BY LinkID", (cid,)):
                print(f"   link -> {OWNER_OF_CODE.get(owner_type, f'type {owner_type}')} {owner} {quality}")
            for media, folder, file in conn.execute(
                    "SELECT m.MediaID, m.MediaPath, m.MediaFile FROM MediaLinkTable l JOIN MultimediaTable m"
                    " USING (MediaID) WHERE l.OwnerType = ? AND l.OwnerID = ? ORDER BY l.LinkID",
                    (OWNER_MEDIA_CITATION, cid)):
                print(f"   scan M{media}: {folder}\\{file}")
    finally:
        conn.close()
    return 0


def create(path: Path, args) -> int:
    problems = []
    fields = parse_assignments(args.field, "--field", problems)
    sets = parse_assignments(args.set, "--set", problems)
    check_sets(sets, problems)
    text = read_text(args.text_file) if args.text_file else ""
    links = []
    for item in args.link:
        parts = item.split(":")
        if len(parts) != 3 or parts[0] not in OWNER_TYPES or not parts[1].isdigit():
            problems.append(f"--link {item!r} is not KIND:ID:QUALITY (kind {', '.join(OWNER_TYPES)})")
            continue
        if len(parts[2]) != 3:
            problems.append(f"quality {parts[2]!r} is not three characters")
        links.append((parts[0], int(parts[1]), parts[2]))

    conn = connect_readonly(path)
    try:
        source = conn.execute("SELECT Name FROM SourceTable WHERE SourceID = ?", (args.source,)).fetchone()
        if source is None:
            print(f"S{args.source} not found")
            return 1
        names = citation_field_names(conn, args.source)
        problems += [f"{n!r} is not a citation field of the source's template ({', '.join(names)})"
                     for n in fields if n not in names]
        name = citation_name(names, fields)
        for kind, owner, _ in links:
            _, table, key = OWNER_TYPES[kind]
            if not conn.execute(f"SELECT 1 FROM {table} WHERE {key} = ?", (owner,)).fetchone():
                problems.append(f"{kind} {owner} not found")
        same = conn.execute("SELECT CitationID FROM CitationTable WHERE SourceID = ? AND CitationName = ?",
                            (args.source, name)).fetchone()
        if same:
            problems.append(f"C{same[0]} of S{args.source} already has this CitationName")
    finally:
        conn.close()

    print(f"New citation under S{args.source} '{source[0]}':")
    for n in names:
        if n in fields:
            print(f"   field {n}: {fields[n]}")
    print(f"   CitationName: {name}")
    print(f"   ActualText: {text!r}")
    for column, value in sets.items():
        print(f"   {column}: {value!r}")
    for kind, owner, quality in links:
        print(f"   link -> {kind} {owner} {quality}")
    if problems:
        print("Refused:\n   " + "\n   ".join(problems))
        return 1
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()

    def write(conn) -> int:
        values = {column: sets.get(column, "") for column in SET_COLUMNS}
        cid = conn.execute(
            "INSERT INTO CitationTable (SourceID, Comments, ActualText, RefNumber, Footnote, ShortFootnote,"
            " Bibliography, Fields, UTCModDate, CitationName) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (args.source, values["Comments"], text, values["RefNumber"], values["Footnote"],
             values["ShortFootnote"], values["Bibliography"],
             fields_blob({n: fields[n] for n in names if n in fields}, declaration=False), stamp, name)).lastrowid
        for kind, owner, quality in links:
            conn.execute("INSERT INTO CitationLinkTable (CitationID, OwnerType, OwnerID, SortOrder, Quality,"
                         " IsPrivate, Flags, UTCModDate) VALUES (?, ?, ?, 0, ?, 0, 0, ?)",
                         (cid, OWNER_TYPES[kind][0], owner, quality, stamp))
        return cid

    print(f"Applied: citation C{write_changes(path, write)}.")
    return 0


def edit(path: Path, args) -> int:
    problems = []
    new_fields = parse_assignments(args.field, "--field", problems)
    sets = parse_assignments(args.set, "--set", problems)
    check_sets(sets, problems)
    if args.text_file:
        sets["ActualText"] = read_text(args.text_file)
    if not (new_fields or sets):
        problems.append("nothing to change: give --field, --set or --text-file")

    conn = connect_readonly(path)
    try:
        row = conn.execute("SELECT SourceID, CitationName, Fields, " + ", ".join(sets or ["Comments"])
                           + " FROM CitationTable WHERE CitationID = ?", (args.id,)).fetchone()
        if row is None:
            print(f"C{args.id} not found")
            return 1
        source, old_name, blob = row[:3]
        old_values = dict(zip(sets or ["Comments"], row[3:]))
        names = citation_field_names(conn, source)
        problems += [f"{n!r} is not a citation field of the source's template ({', '.join(names)})"
                     for n in new_fields if n not in names]
        old_fields = read_fields(blob)
        fields = {**old_fields, **new_fields}
        name = citation_name(names, fields) if new_fields else old_name
        same = conn.execute("SELECT CitationID FROM CitationTable WHERE SourceID = ? AND CitationName = ?"
                            " AND CitationID != ?", (source, name, args.id)).fetchone()
        if new_fields and same:
            problems.append(f"C{same[0]} of S{source} already has CitationName {name!r}")
    finally:
        conn.close()

    print(f"C{args.id} (S{source}):")
    for field, value in new_fields.items():
        print(f"   field {field}: {old_fields.get(field)!r} -> {value!r}")
    if new_fields:
        print(f"   CitationName: {old_name!r} -> {name!r}")
    for column, value in sets.items():
        print(f"   {column}: {old_values[column]!r} -> {value!r}")
    if problems:
        print("Refused:\n   " + "\n   ".join(problems))
        return 1
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()

    def write(conn) -> None:
        assignments = {**sets, "UTCModDate": stamp}
        if new_fields:
            assignments.update(Fields=fields_blob(fields, declaration=False), CitationName=name)
        conn.execute("UPDATE CitationTable SET " + ", ".join(f"{c} = ?" for c in assignments)
                     + " WHERE CitationID = ?", [*assignments.values(), args.id])

    write_changes(path, write)
    print(f"Applied: citation C{args.id} changed.")
    return 0


def delete(path: Path, args) -> int:
    conn = connect_readonly(path)
    try:
        row = conn.execute("SELECT CitationName FROM CitationTable WHERE CitationID = ?", (args.id,)).fetchone()
        if row is None:
            print(f"C{args.id} not found")
            return 1
        links = conn.execute("SELECT COUNT(*) FROM CitationLinkTable WHERE CitationID = ?", (args.id,)).fetchone()[0]
        scans = conn.execute("SELECT COUNT(*) FROM MediaLinkTable WHERE OwnerType = ? AND OwnerID = ?",
                             (OWNER_MEDIA_CITATION, args.id)).fetchone()[0]
    finally:
        conn.close()

    print(f"Delete citation C{args.id} '{row[0]}': {links} links, {scans} scans")
    problems = []
    if scans:
        problems.append(f"{scans} scans are attached; remove their media links first")
    if links and not args.with_links:
        problems.append(f"{links} links; give --with-links to delete them too")
    if problems:
        print("Refused:\n   " + "\n   ".join(problems))
        return 1
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    def write(conn) -> None:
        conn.execute("DELETE FROM CitationLinkTable WHERE CitationID = ?", (args.id,))
        conn.execute("DELETE FROM CitationTable WHERE CitationID = ?", (args.id,))

    write_changes(path, write)
    print(f"Applied: citation C{args.id} deleted.")
    return 0


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="citation.py PATH_TO_RMTREE")
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("get")
    p.add_argument("ids", nargs="*", type=int)
    p.add_argument("--source", type=int)
    p.set_defaults(run=get)

    p = commands.add_parser("create")
    p.add_argument("--source", type=int, required=True)
    p.add_argument("--field", action="append", default=[])
    p.add_argument("--set", action="append", default=[])
    p.add_argument("--text-file")
    p.add_argument("--link", action="append", default=[])
    p.set_defaults(run=create)

    p = commands.add_parser("edit")
    p.add_argument("id", type=int)
    p.add_argument("--field", action="append", default=[])
    p.add_argument("--set", action="append", default=[])
    p.add_argument("--text-file")
    p.set_defaults(run=edit)

    p = commands.add_parser("delete")
    p.add_argument("id", type=int)
    p.add_argument("--with-links", action="store_true")
    p.set_defaults(run=delete)

    for name in ("create", "edit", "delete"):
        commands.choices[name].add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])
    if args.command == "get" and not args.ids and args.source is None:
        parser.error("get needs citation IDs or --source")
    return args.run(path, args)


if __name__ == "__main__":
    sys.exit(main())
