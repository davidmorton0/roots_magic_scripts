"""Get, create, edit or delete sources (SourceTable).

  get     ID [ID ...] | --name TEXT     Print sources (read-only); --name matches part of the name.
  create  --name NAME [--template ID] [--field NAME=VALUE ...] [--set COLUMN=VALUE ...]
  edit    ID [--name NAME] [--field NAME=VALUE ...] [--set COLUMN=VALUE ...]
  delete  ID

--template is a SourceTemplateTable ID; 0 (the default) is a free-form source. --field sets a source
field of the template (not a citation field); a free-form source has Footnote, ShortFootnote and
Bibliography. Other fields already in the row are kept. Fields is written without a declaration, as
RootsMagic 12 saves source rows. --set sets RefNumber, ActualText (the source text) or Comments (the
note). The template of an existing source is not changed here.

Refused when another source has the name (any case), a field is not a source field of the template,
the template does not exist, a source does not exist, or (delete) the source still has citations,
media, tasks, web links or addresses.

SourceTable.Name is in an RMNOCASE index: run RootsMagic's rebuild indexes after create or edit.

create, edit and delete are dry runs by default: they print what would change. --apply writes it in
one transaction. RootsMagic must be closed, and the file must be a working copy.

Usage: python source.py PATH_TO_RMTREE get|create|edit|delete ... [--apply]
"""

import argparse
import sys
from pathlib import Path

from rmutils import (
    connect_readonly,
    db_path_arg,
    fields_blob,
    parse_assignments,
    read_fields,
    template_fields,
    utc_mod_date,
    write_changes,
)

OWNER_SOURCE = 3
FREE_FORM_FIELDS = ["Footnote", "ShortFootnote", "Bibliography"]
SET_COLUMNS = ("RefNumber", "ActualText", "Comments")
USES = {
    "citations": "SELECT COUNT(*) FROM CitationTable WHERE SourceID = ?",
    "media": "SELECT COUNT(*) FROM MediaLinkTable WHERE OwnerType = 3 AND OwnerID = ?",
    "tasks": "SELECT COUNT(*) FROM TaskLinkTable WHERE OwnerType = 3 AND OwnerID = ?",
    "web links": "SELECT COUNT(*) FROM URLTable WHERE OwnerType = 3 AND OwnerID = ?",
    "addresses": "SELECT COUNT(*) FROM AddressLinkTable WHERE OwnerType = 3 AND OwnerID = ?",
}


def source_field_names(conn, template: int) -> list[str] | None:
    """Source fields of the template in order; None if the template does not exist."""
    if not template:
        return FREE_FORM_FIELDS
    fields = template_fields(conn, template)
    return [n for n, is_citation in fields if not is_citation] if fields else None


def check_sets(sets: dict[str, str], problems: list[str]) -> None:
    for column in [c for c in sets if c not in SET_COLUMNS]:
        problems.append(f"--set {column!r} is not one of {', '.join(SET_COLUMNS)}")
        del sets[column]


def get(path: Path, args) -> int:
    conn = connect_readonly(path)
    try:
        ids = args.ids or [r[0] for r in conn.execute(
            "SELECT SourceID FROM SourceTable WHERE Name LIKE ? ORDER BY SourceID", (f"%{args.name}%",))]
        if not ids:
            print("No sources found")
            return 1
        for sid in ids:
            row = conn.execute("SELECT Name, RefNumber, ActualText, Comments, IsPrivate, TemplateID, Fields,"
                               " UTCModDate FROM SourceTable WHERE SourceID = ?", (sid,)).fetchone()
            if row is None:
                print(f"S{sid} not found")
                return 1
            name, ref, text, comments, private, template, blob, stamp = row
            print(f"S{sid}  '{name}'  (template {template}, IsPrivate {private})")
            for label, value in (("RefNumber", ref), ("ActualText", text), ("Comments", comments)):
                if value:
                    print(f"   {label}: {value!r}")
            for field, value in read_fields(blob).items():
                print(f"   field {field}: {value}")
            print(f"   UTCModDate: {stamp}")
            for kind, sql in USES.items():
                count = conn.execute(sql, (sid,)).fetchone()[0]
                if count:
                    print(f"   {kind}: {count}")
    finally:
        conn.close()
    return 0


def create(path: Path, args) -> int:
    problems = []
    fields = parse_assignments(args.field, "--field", problems)
    sets = parse_assignments(args.set, "--set", problems)
    check_sets(sets, problems)
    conn = connect_readonly(path)
    try:
        names = source_field_names(conn, args.template)
        if names is None:
            problems.append(f"template {args.template} not found")
            names = []
        problems += [f"{n!r} is not a source field of template {args.template} ({', '.join(names)})"
                     for n in fields if n not in names]
        clash = conn.execute("SELECT SourceID FROM SourceTable WHERE Name = ? COLLATE NOCASE",
                             (args.name,)).fetchone()
        if clash:
            problems.append(f"S{clash[0]} is already named {args.name!r}")
    finally:
        conn.close()

    print(f"New source '{args.name}' (template {args.template})")
    for n in names:
        if n in fields:
            print(f"   field {n}: {fields[n]}")
    for column, value in sets.items():
        print(f"   {column}: {value!r}")
    if problems:
        print("Refused:\n   " + "\n   ".join(problems))
        return 1
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()

    def write(conn) -> int:
        return conn.execute(
            "INSERT INTO SourceTable (Name, RefNumber, ActualText, Comments, IsPrivate, TemplateID, Fields,"
            " UTCModDate) VALUES (?, ?, ?, ?, 0, ?, ?, ?)",
            (args.name, sets.get("RefNumber", ""), sets.get("ActualText", ""), sets.get("Comments", ""),
             args.template, fields_blob({n: fields[n] for n in names if n in fields}, declaration=False),
             stamp)).lastrowid

    print(f"Applied: source S{write_changes(path, write)}.")
    return 0


def edit(path: Path, args) -> int:
    problems = []
    new_fields = parse_assignments(args.field, "--field", problems)
    sets = parse_assignments(args.set, "--set", problems)
    check_sets(sets, problems)
    if args.name is not None:
        sets["Name"] = args.name
    if not (new_fields or sets):
        problems.append("nothing to change: give --name, --field or --set")

    conn = connect_readonly(path)
    try:
        columns = ["Name", *sets] if "Name" not in sets else list(sets)
        row = conn.execute("SELECT TemplateID, Fields, " + ", ".join(columns)
                           + " FROM SourceTable WHERE SourceID = ?", (args.id,)).fetchone()
        if row is None:
            print(f"S{args.id} not found")
            return 1
        template, blob = row[:2]
        old_values = dict(zip(columns, row[2:]))
        names = source_field_names(conn, template) or []
        problems += [f"{n!r} is not a source field of template {template} ({', '.join(names)})"
                     for n in new_fields if n not in names]
        old_fields = read_fields(blob)
        if args.name is not None:
            clash = conn.execute("SELECT SourceID FROM SourceTable WHERE Name = ? COLLATE NOCASE"
                                 " AND SourceID <> ?", (args.name, args.id)).fetchone()
            if clash:
                problems.append(f"S{clash[0]} is already named {args.name!r}")
    finally:
        conn.close()

    print(f"S{args.id} '{old_values['Name']}':")
    for field, value in new_fields.items():
        print(f"   field {field}: {old_fields.get(field)!r} -> {value!r}")
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
            assignments["Fields"] = fields_blob({**old_fields, **new_fields}, declaration=False)
        conn.execute("UPDATE SourceTable SET " + ", ".join(f"{c} = ?" for c in assignments)
                     + " WHERE SourceID = ?", [*assignments.values(), args.id])

    write_changes(path, write)
    print(f"Applied: source S{args.id} changed. Run RootsMagic's rebuild indexes.")
    return 0


def delete(path: Path, args) -> int:
    conn = connect_readonly(path)
    try:
        row = conn.execute("SELECT Name FROM SourceTable WHERE SourceID = ?", (args.id,)).fetchone()
        uses = {kind: conn.execute(sql, (args.id,)).fetchone()[0] for kind, sql in USES.items()}
    finally:
        conn.close()
    if row is None:
        print(f"S{args.id} not found")
        return 1
    used = {k: n for k, n in uses.items() if n}
    if used:
        print(f"Refused: S{args.id} '{row[0]}' is still used: {used}")
        return 1
    print(f"Delete S{args.id} '{row[0]}' (no citations or attachments)")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0
    write_changes(path, lambda conn: conn.execute("DELETE FROM SourceTable WHERE SourceID = ?", (args.id,)))
    print(f"Applied: source S{args.id} deleted.")
    return 0


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="source.py PATH_TO_RMTREE")
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("get")
    p.add_argument("ids", nargs="*", type=int)
    p.add_argument("--name")
    p.set_defaults(run=get)

    p = commands.add_parser("create")
    p.add_argument("--name", required=True)
    p.add_argument("--template", type=int, default=0)
    p.add_argument("--field", action="append", default=[])
    p.add_argument("--set", action="append", default=[])
    p.set_defaults(run=create)

    p = commands.add_parser("edit")
    p.add_argument("id", type=int)
    p.add_argument("--name")
    p.add_argument("--field", action="append", default=[])
    p.add_argument("--set", action="append", default=[])
    p.set_defaults(run=edit)

    p = commands.add_parser("delete")
    p.add_argument("id", type=int)
    p.set_defaults(run=delete)

    for name in ("create", "edit", "delete"):
        commands.choices[name].add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])
    if args.command == "get" and not args.ids and args.name is None:
        parser.error("get needs source IDs or --name")
    return args.run(path, args)


if __name__ == "__main__":
    sys.exit(main())
