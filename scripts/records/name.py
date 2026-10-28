"""Get, create, edit or delete names (NameTable). create makes alternative names; the primary name is
made with the person (person.py create).

  get     ID [ID ...] | --person ID        Print names (read-only).
  create  --person ID --given GIVEN --surname SURNAME [--prefix P] [--suffix S] [--nickname N]
          [--type N] [--note TEXT]
  edit    ID [--given G] [--surname S] [--prefix P] [--suffix S] [--nickname N] [--type N] [--note TEXT]
  delete  ID [--with-links]

--type is NameTable.NameType; 1 is AKA (alternative name), the default (confirmed from a name made
by hand). A new name has no date, IsPrimary 0 and BirthYear copied from the person's primary name, as
alternative names written earlier. GivenMP and SurnameMP follow Given and Surname on edit when they
held the old value. Cite a name with citation_link.py create --owner name:ID.

Refused when the person or name does not exist, the person already has a name with the same given
names and surname (create), or (delete) the name is primary, or has citation links and --with-links
is not given.

Surname and Given are in RMNOCASE indexes: run RootsMagic's rebuild indexes after create or edit.

create, edit and delete are dry runs by default: they print what would change. --apply writes it in
one transaction. RootsMagic must be closed, and the file must be a working copy.

Usage: python name.py PATH_TO_RMTREE get|create|edit|delete ... [--apply]
"""

import argparse
import sys
from pathlib import Path

from rmutils import (
    NO_DATE,
    NO_SORT_DATE,
    connect_readonly,
    db_path_arg,
    stop_unless_applying,
    utc_mod_date,
    write_changes,
)

NAME_AKA, OWNER_NAME = 1, 7
TEXT_COLUMNS = {"given": "Given", "surname": "Surname", "prefix": "Prefix", "suffix": "Suffix",
                "nickname": "Nickname", "note": "Note"}


def describe(row) -> str:
    nid, owner, given, surname, prefix, suffix, nickname, kind, primary = row
    text = " ".join(p for p in (prefix, given, surname) if p) + (f", {suffix}" if suffix else "")
    extra = f" nickname {nickname!r}" if nickname else ""
    return f"N{nid}: P{owner} {text}{extra} (NameType {kind}{', primary' if primary else ''})"


COLUMNS = "NameID, OwnerID, Given, Surname, Prefix, Suffix, Nickname, NameType, IsPrimary"


def get(path: Path, args) -> int:
    conn = connect_readonly(path)
    try:
        if args.ids:
            rows = [conn.execute(f"SELECT {COLUMNS} FROM NameTable WHERE NameID = ?", (i,)).fetchone()
                    for i in args.ids]
            if None in rows:
                print("Names not found: " + ", ".join(f"N{i}" for i, r in zip(args.ids, rows) if r is None))
                return 1
        else:
            rows = conn.execute(f"SELECT {COLUMNS} FROM NameTable WHERE OwnerID = ? ORDER BY IsPrimary DESC, NameID",
                                (args.person,)).fetchall()
            if not rows:
                print("No names found")
                return 1
    finally:
        conn.close()
    for row in rows:
        print(describe(row))
    return 0


def create(path: Path, args) -> int:
    problems = []
    conn = connect_readonly(path)
    try:
        names = conn.execute("SELECT Given, Surname, IsPrimary, BirthYear FROM NameTable WHERE OwnerID = ?",
                             (args.person,)).fetchall()
        if not names:
            problems.append(f"P{args.person} not found")
        if any(g.casefold() == args.given.casefold() and s.casefold() == args.surname.casefold()
               for g, s, _, _ in names):
            problems.append(f"P{args.person} already has the name {args.given} {args.surname}")
    finally:
        conn.close()
    primary = next((n for n in names if n[2] == 1), names[0] if names else (None, None, None, 0))
    print(f"New name for P{args.person} ({primary[0]} {primary[1]}): {args.given} {args.surname}"
          f" (NameType {args.type})")
    for label, value in (("Prefix", args.prefix), ("Suffix", args.suffix), ("Nickname", args.nickname),
                         ("Note", args.note)):
        if value:
            print(f"   {label}: {value!r}")
    done = stop_unless_applying(problems, args.apply)
    if done is not None:
        return done

    stamp = utc_mod_date()

    def write(conn) -> int:
        return conn.execute(
            "INSERT INTO NameTable (OwnerID, Surname, Given, Prefix, Suffix, Nickname, NameType, Date, SortDate,"
            " IsPrimary, IsPrivate, Proof, Sentence, Note, BirthYear, DeathYear, Display, Language, UTCModDate,"
            " SurnameMP, GivenMP, NicknameMP) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, '', ?, ?, 0, 0, '', ?,"
            " ?, ?, '')", (args.person, args.surname, args.given, args.prefix or "", args.suffix or "",
                           args.nickname or "", args.type, NO_DATE, NO_SORT_DATE, args.note or "",
                           primary[3] or 0, stamp, args.surname, args.given)).lastrowid

    print(f"Applied: name N{write_changes(path, write)}. Run RootsMagic's rebuild indexes.")
    return 0


def edit(path: Path, args) -> int:
    changes = {column: getattr(args, option) for option, column in TEXT_COLUMNS.items()
               if getattr(args, option) is not None}
    if args.type is not None:
        changes["NameType"] = args.type
    problems = [] if changes else ["nothing to change: give a name part, --type or --note"]
    conn = connect_readonly(path)
    try:
        row = conn.execute("SELECT Given, Surname, GivenMP, SurnameMP, " + ", ".join(changes or ["Note"])
                           + " FROM NameTable WHERE NameID = ?", (args.id,)).fetchone()
        if row is None:
            print(f"N{args.id} not found")
            return 1
        given, surname, given_mp, surname_mp = row[:4]
        old = dict(zip(changes or ["Note"], row[4:]))
    finally:
        conn.close()
    if "Given" in changes and given_mp == given:
        changes["GivenMP"] = changes["Given"]
    if "Surname" in changes and surname_mp == surname:
        changes["SurnameMP"] = changes["Surname"]
    print(f"N{args.id} ({given} {surname}):")
    for column, value in changes.items():
        print(f"   {column}: {old.get(column, '(follows)')!r} -> {value!r}")
    done = stop_unless_applying(problems, args.apply)
    if done is not None:
        return done

    def write(conn) -> None:
        assignments = {**changes, "UTCModDate": utc_mod_date()}
        conn.execute("UPDATE NameTable SET " + ", ".join(f"{c} = ?" for c in assignments) + " WHERE NameID = ?",
                     [*assignments.values(), args.id])

    write_changes(path, write)
    print(f"Applied: name N{args.id} changed. Run RootsMagic's rebuild indexes.")
    return 0


def delete(path: Path, args) -> int:
    conn = connect_readonly(path)
    try:
        row = conn.execute(f"SELECT {COLUMNS} FROM NameTable WHERE NameID = ?", (args.id,)).fetchone()
        if row is None:
            print(f"N{args.id} not found")
            return 1
        links = conn.execute("SELECT COUNT(*) FROM CitationLinkTable WHERE OwnerType = ? AND OwnerID = ?",
                             (OWNER_NAME, args.id)).fetchone()[0]
    finally:
        conn.close()
    print("Delete " + describe(row) + f", {links} citation links")
    problems = []
    if row[8]:
        problems.append("the primary name cannot be deleted; delete the person (person.py delete)")
    if links and not args.with_links:
        problems.append(f"{links} citation links; give --with-links to delete them too")
    done = stop_unless_applying(problems, args.apply)
    if done is not None:
        return done

    def write(conn) -> None:
        conn.execute("DELETE FROM CitationLinkTable WHERE OwnerType = ? AND OwnerID = ?", (OWNER_NAME, args.id))
        conn.execute("DELETE FROM NameTable WHERE NameID = ?", (args.id,))

    write_changes(path, write)
    print(f"Applied: name N{args.id} deleted.")
    return 0


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="name.py PATH_TO_RMTREE")
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("get")
    p.add_argument("ids", nargs="*", type=int)
    p.add_argument("--person", type=int)
    p.set_defaults(run=get)

    p = commands.add_parser("create")
    p.add_argument("--person", type=int, required=True)
    p.add_argument("--given", required=True)
    p.add_argument("--surname", required=True)
    p.set_defaults(run=create)

    p = commands.add_parser("edit")
    p.add_argument("id", type=int)
    p.add_argument("--given")
    p.add_argument("--surname")
    p.set_defaults(run=edit)

    p = commands.add_parser("delete")
    p.add_argument("id", type=int)
    p.add_argument("--with-links", action="store_true")
    p.set_defaults(run=delete)

    for name in ("create", "edit"):
        sub = commands.choices[name]
        for option in ("prefix", "suffix", "nickname", "note"):
            sub.add_argument(f"--{option}")
    commands.choices["create"].add_argument("--type", type=int, default=NAME_AKA)
    commands.choices["edit"].add_argument("--type", type=int)
    for name in ("create", "edit", "delete"):
        commands.choices[name].add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])
    if args.command == "get" and not args.ids and args.person is None:
        parser.error("get needs name IDs or --person")
    return args.run(path, args)


if __name__ == "__main__":
    sys.exit(main())
