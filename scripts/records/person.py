"""Get, create, edit or delete people (PersonTable). A new person gets a primary name (NameTable).

  get     ID [ID ...] | --name TEXT      Print people (read-only); --name matches part of any name.
  create  --given GIVEN --surname SURNAME --sex male|female|unknown [--prefix P] [--suffix S] [--note TEXT]
  edit    ID [--sex male|female|unknown] [--note TEXT] [--living 0|1] [--private 0|1]
  delete  ID

New rows copy the one-off person scripts (not yet checked against a person made by hand in
RootsMagic): UniqueID 32 hex digits plus a checksum, Sex 0 male / 1 female / 2 unknown, ParentID and
SpouseID 0 (family.py sets them), Living, IsPrivate, Proof, Bookmark and the colours 0; primary name
NameType 0, no date, BirthYear and DeathYear 0, SurnameMP and GivenMP the same as Surname and Given.
Names are changed with name.py and links to families with family.py. Other people with the same
name are listed but do not stop create.

Refused when a person does not exist, or (delete) the person still has alternative names, events,
a family, a parent family, witness entries, citations, media, tasks, web links or addresses. Delete
removes the person and the primary name.

Surname and Given are in RMNOCASE indexes: run RootsMagic's rebuild indexes after create.

create, edit and delete are dry runs by default: they print what would change. --apply writes it in
one transaction. RootsMagic must be closed, and the file must be a working copy.

Usage: python person.py PATH_TO_RMTREE get|create|edit|delete ... [--apply]
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
    unique_id,
    utc_mod_date,
    write_changes,
)

SEX = {"male": 0, "female": 1, "unknown": 2}
SEX_NAME = {code: name for name, code in SEX.items()}
OWNER_PERSON = 0
USES = {
    "alternative names": "SELECT COUNT(*) FROM NameTable WHERE OwnerID = ?1 AND IsPrimary = 0",
    "events": "SELECT COUNT(*) FROM EventTable WHERE OwnerType = 0 AND OwnerID = ?1",
    "families as a partner": "SELECT COUNT(*) FROM FamilyTable WHERE FatherID = ?1 OR MotherID = ?1",
    "parent families": "SELECT COUNT(*) FROM ChildTable WHERE ChildID = ?1",
    "witness entries": "SELECT COUNT(*) FROM WitnessTable WHERE PersonID = ?1",
    "citations": "SELECT COUNT(*) FROM CitationLinkTable WHERE OwnerType = 0 AND OwnerID = ?1",
    "name citations": "SELECT COUNT(*) FROM CitationLinkTable l JOIN NameTable n ON l.OwnerType = 7"
                      " AND l.OwnerID = n.NameID WHERE n.OwnerID = ?1",
    "media": "SELECT COUNT(*) FROM MediaLinkTable WHERE OwnerType = 0 AND OwnerID = ?1",
    "tasks": "SELECT COUNT(*) FROM TaskLinkTable WHERE OwnerType = 0 AND OwnerID = ?1",
    "web links": "SELECT COUNT(*) FROM URLTable WHERE OwnerType = 0 AND OwnerID = ?1",
    "addresses": "SELECT COUNT(*) FROM AddressLinkTable WHERE OwnerType = 0 AND OwnerID = ?1",
}


def uses(conn, pid: int) -> dict[str, int]:
    return {kind: conn.execute(sql, (pid,)).fetchone()[0] for kind, sql in USES.items()}


def primary_name(conn, pid: int) -> str:
    row = conn.execute("SELECT Prefix, Given, Surname, Suffix FROM NameTable WHERE OwnerID = ? AND IsPrimary = 1",
                       (pid,)).fetchone()
    return " ".join(p for p in (row[0], row[1], row[2]) if p) + (f", {row[3]}" if row[3] else "") if row \
        else "(no primary name)"


def get(path: Path, args) -> int:
    conn = connect_readonly(path)
    try:
        ids = args.ids or [r[0] for r in conn.execute(
            "SELECT DISTINCT OwnerID FROM NameTable WHERE Given LIKE ?1 OR Surname LIKE ?1"
            " OR Given || ' ' || Surname LIKE ?1 ORDER BY OwnerID", (f"%{args.name}%",))]
        if not ids:
            print("No people found")
            return 1
        for pid in ids:
            row = conn.execute("SELECT Sex, ParentID, SpouseID, Living, IsPrivate, Note, UTCModDate FROM PersonTable"
                               " WHERE PersonID = ?", (pid,)).fetchone()
            if row is None:
                print(f"P{pid} not found")
                return 1
            sex, parent, spouse, living, private, note, stamp = row
            print(f"P{pid}  {primary_name(conn, pid)}  (sex {SEX_NAME.get(sex, sex)}, ParentID F{parent},"
                  f" SpouseID F{spouse}, Living {living}, IsPrivate {private})")
            for nid, given, surname, kind, primary in conn.execute(
                    "SELECT NameID, Given, Surname, NameType, IsPrimary FROM NameTable WHERE OwnerID = ?"
                    " ORDER BY IsPrimary DESC, NameID", (pid,)):
                print(f"   name N{nid}{' (primary)' if primary else ''}: {given} {surname} (NameType {kind})")
            if note:
                print(f"   Note: {note!r}")
            for fam, in conn.execute("SELECT FamilyID FROM FamilyTable WHERE FatherID = ?1 OR MotherID = ?1",
                                     (pid,)):
                print(f"   partner in F{fam}")
            for fam, in conn.execute("SELECT FamilyID FROM ChildTable WHERE ChildID = ?", (pid,)):
                print(f"   child of F{fam}")
            counts = {k: n for k, n in uses(conn, pid).items() if n and k not in ("alternative names",
                      "families as a partner", "parent families")}
            if counts:
                print("   uses: " + ", ".join(f"{k} {n}" for k, n in counts.items()))
            print(f"   UTCModDate: {stamp}")
    finally:
        conn.close()
    return 0


def create(path: Path, args) -> int:
    conn = connect_readonly(path)
    try:
        same = [r[0] for r in conn.execute(
            "SELECT DISTINCT OwnerID FROM NameTable WHERE Given = ? AND Surname = ? ORDER BY OwnerID",
            (args.given, args.surname))]
    finally:
        conn.close()
    print(f"New person: {args.given} {args.surname}, sex {args.sex}")
    for label, value in (("Prefix", args.prefix), ("Suffix", args.suffix), ("Note", args.note)):
        if value:
            print(f"   {label}: {value!r}")
    if same:
        print("   same name already used by " + ", ".join(f"P{p}" for p in same))
    done = stop_unless_applying([], args.apply)
    if done is not None:
        return done

    stamp = utc_mod_date()

    def write(conn) -> int:
        pid = conn.execute(
            "INSERT INTO PersonTable (UniqueID, Sex, ParentID, SpouseID, Color, Color1, Color2, Color3, Color4,"
            " Color5, Color6, Color7, Color8, Color9, Relate1, Relate2, Flags, Living, IsPrivate, Proof, Bookmark,"
            " Note, UTCModDate) VALUES (?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ?, ?)",
            (unique_id(), SEX[args.sex], args.note or "", stamp)).lastrowid
        conn.execute(
            "INSERT INTO NameTable (OwnerID, Surname, Given, Prefix, Suffix, Nickname, NameType, Date, SortDate,"
            " IsPrimary, IsPrivate, Proof, Sentence, Note, BirthYear, DeathYear, Display, Language, UTCModDate,"
            " SurnameMP, GivenMP, NicknameMP) VALUES (?, ?, ?, ?, ?, '', 0, ?, ?, 1, 0, 0, '', '', 0, 0, 0, '', ?,"
            " ?, ?, '')", (pid, args.surname, args.given, args.prefix or "", args.suffix or "", NO_DATE,
                           NO_SORT_DATE, stamp, args.surname, args.given))
        return pid

    print(f"Applied: person P{write_changes(path, write)}. Run RootsMagic's rebuild indexes.")
    return 0


def edit(path: Path, args) -> int:
    changes = {}
    if args.sex is not None:
        changes["Sex"] = SEX[args.sex]
    if args.note is not None:
        changes["Note"] = args.note
    if args.living is not None:
        changes["Living"] = args.living
    if args.private is not None:
        changes["IsPrivate"] = args.private
    problems = [] if changes else ["nothing to change: give --sex, --note, --living or --private"]
    conn = connect_readonly(path)
    try:
        row = conn.execute("SELECT " + ", ".join(changes or ["Sex"]) + " FROM PersonTable WHERE PersonID = ?",
                           (args.id,)).fetchone()
        if row is None:
            print(f"P{args.id} not found")
            return 1
        old = dict(zip(changes or ["Sex"], row))
        name = primary_name(conn, args.id)
    finally:
        conn.close()
    print(f"P{args.id} {name}:")
    for column, value in changes.items():
        print(f"   {column}: {old[column]!r} -> {value!r}")
    done = stop_unless_applying(problems, args.apply)
    if done is not None:
        return done

    def write(conn) -> None:
        assignments = {**changes, "UTCModDate": utc_mod_date()}
        conn.execute("UPDATE PersonTable SET " + ", ".join(f"{c} = ?" for c in assignments)
                     + " WHERE PersonID = ?", [*assignments.values(), args.id])

    write_changes(path, write)
    print(f"Applied: person P{args.id} changed.")
    return 0


def delete(path: Path, args) -> int:
    conn = connect_readonly(path)
    try:
        if not conn.execute("SELECT 1 FROM PersonTable WHERE PersonID = ?", (args.id,)).fetchone():
            print(f"P{args.id} not found")
            return 1
        name = primary_name(conn, args.id)
        used = {k: n for k, n in uses(conn, args.id).items() if n}
    finally:
        conn.close()
    print(f"Delete person P{args.id} {name}")
    done = stop_unless_applying([f"still used: {used}"] if used else [], args.apply)
    if done is not None:
        return done

    def write(conn) -> None:
        conn.execute("DELETE FROM NameTable WHERE OwnerID = ?", (args.id,))
        conn.execute("DELETE FROM PersonTable WHERE PersonID = ?", (args.id,))

    write_changes(path, write)
    print(f"Applied: person P{args.id} deleted.")
    return 0


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="person.py PATH_TO_RMTREE")
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("get")
    p.add_argument("ids", nargs="*", type=int)
    p.add_argument("--name")
    p.set_defaults(run=get)

    p = commands.add_parser("create")
    p.add_argument("--given", required=True)
    p.add_argument("--surname", required=True)
    p.add_argument("--sex", choices=list(SEX), required=True)
    p.add_argument("--prefix")
    p.add_argument("--suffix")
    p.add_argument("--note")
    p.set_defaults(run=create)

    p = commands.add_parser("edit")
    p.add_argument("id", type=int)
    p.add_argument("--sex", choices=list(SEX))
    p.add_argument("--note")
    p.add_argument("--living", type=int, choices=(0, 1))
    p.add_argument("--private", type=int, choices=(0, 1))
    p.set_defaults(run=edit)

    p = commands.add_parser("delete")
    p.add_argument("id", type=int)
    p.set_defaults(run=delete)

    for name in ("create", "edit", "delete"):
        commands.choices[name].add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])
    if args.command == "get" and not args.ids and args.name is None:
        parser.error("get needs person IDs or --name")
    return args.run(path, args)


if __name__ == "__main__":
    sys.exit(main())
