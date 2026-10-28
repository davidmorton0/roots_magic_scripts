"""Get, create, edit or delete families (FamilyTable) and their children (ChildTable).

  get     ID [ID ...] | --person ID      Print families (read-only); --person finds those the person is a
                                         partner or child in.
  create  [--father ID] [--mother ID] [--child ID ...] [--set Note=TEXT]
  edit    ID [--father ID] [--mother ID] [--add-child ID ...] [--remove-child ID ...] [--set Note=TEXT]
  delete  ID

A family needs a father or a mother (0 or left out for none). Children are added to ChildTable
in order after the existing ones. PersonTable.SpouseID (a partner's family) and ParentID (a child's
family) are set when 0, and moved to another family of the person, or 0, when the person leaves
the family. FamilyTable.ChildID (RootsMagic's reference to a child, filled on old families) is left
as it is, except that it is cleared when that child is removed. New rows copy the one-off scripts
(not yet checked against a family made by hand): ChildID, HusbOrder, WifeOrder, IsPrivate, Proof and
the labels 0 or empty; child rows RelFather and RelMother 0.

Refused when a person or family does not exist, a family with the same father and mother exists
(create), a child is a partner of the family, a child is already (or not) in the family, or (delete)
the family has events, citations, media, tasks, web links or addresses. Delete removes the family
and its child rows, not the people.

create, edit and delete are dry runs by default: they print what would change. --apply writes it in
one transaction. RootsMagic must be closed, and the file must be a working copy.

Usage: python family.py PATH_TO_RMTREE get|create|edit|delete ... [--apply]
"""

import argparse
import sys
from pathlib import Path

from rmutils import (
    connect_readonly,
    db_path_arg,
    parse_assignments,
    person_names,
    stop_unless_applying,
    utc_mod_date,
    write_changes,
)

OWNER_FAMILY = 1
USES = {
    "events": "SELECT COUNT(*) FROM EventTable WHERE OwnerType = 1 AND OwnerID = ?",
    "citations": "SELECT COUNT(*) FROM CitationLinkTable WHERE OwnerType = 1 AND OwnerID = ?",
    "media": "SELECT COUNT(*) FROM MediaLinkTable WHERE OwnerType = 1 AND OwnerID = ?",
    "tasks": "SELECT COUNT(*) FROM TaskLinkTable WHERE OwnerType = 1 AND OwnerID = ?",
    "web links": "SELECT COUNT(*) FROM URLTable WHERE OwnerType = 1 AND OwnerID = ?",
    "addresses": "SELECT COUNT(*) FROM AddressLinkTable WHERE OwnerType = 1 AND OwnerID = ?",
}


def label(names: dict[int, str], pid: int) -> str:
    return f"P{pid} {names[pid]}" if pid in names else (f"P{pid} (not found)" if pid else "-")


def move_spouse(conn, pid: int, family: int, stamp: float) -> None:
    """After person pid left family: SpouseID moves to another family of theirs, or 0."""
    other = conn.execute("SELECT MIN(FamilyID) FROM FamilyTable WHERE (FatherID = ?1 OR MotherID = ?1)"
                         " AND FamilyID <> ?2", (pid, family)).fetchone()[0] or 0
    conn.execute("UPDATE PersonTable SET SpouseID = ?, UTCModDate = ? WHERE PersonID = ? AND SpouseID = ?",
                 (other, stamp, pid, family))


def move_parent(conn, pid: int, family: int, stamp: float) -> None:
    """After child pid left family: ParentID moves to another family they are a child in, or 0."""
    other = conn.execute("SELECT MIN(FamilyID) FROM ChildTable WHERE ChildID = ? AND FamilyID <> ?",
                         (pid, family)).fetchone()[0] or 0
    conn.execute("UPDATE PersonTable SET ParentID = ?, UTCModDate = ? WHERE PersonID = ? AND ParentID = ?",
                 (other, stamp, pid, family))


def join_spouse(conn, pid: int, family: int, stamp: float) -> None:
    if pid:
        conn.execute("UPDATE PersonTable SET SpouseID = ?, UTCModDate = ? WHERE PersonID = ? AND SpouseID = 0",
                     (family, stamp, pid))


def add_child(conn, pid: int, family: int, stamp: float) -> None:
    order = conn.execute("SELECT COALESCE(MAX(ChildOrder), 0) + 1 FROM ChildTable WHERE FamilyID = ?",
                         (family,)).fetchone()[0]
    conn.execute("INSERT INTO ChildTable (ChildID, FamilyID, RelFather, RelMother, ChildOrder, IsPrivate,"
                 " ProofFather, ProofMother, Note, UTCModDate) VALUES (?, ?, 0, 0, ?, 0, 0, 0, '', ?)",
                 (pid, family, order, stamp))
    conn.execute("UPDATE PersonTable SET ParentID = ?, UTCModDate = ? WHERE PersonID = ? AND ParentID = 0",
                 (family, stamp, pid))


def get(path: Path, args) -> int:
    conn = connect_readonly(path)
    try:
        names = person_names(conn)
        ids = args.ids or sorted({r[0] for r in conn.execute(
            "SELECT FamilyID FROM FamilyTable WHERE FatherID = ?1 OR MotherID = ?1"
            " UNION SELECT FamilyID FROM ChildTable WHERE ChildID = ?1", (args.person,))})
        if not ids:
            print("No families found")
            return 1
        for fid in ids:
            row = conn.execute("SELECT FatherID, MotherID, ChildID, HusbOrder, WifeOrder, Note, UTCModDate"
                               " FROM FamilyTable WHERE FamilyID = ?", (fid,)).fetchone()
            if row is None:
                print(f"F{fid} not found")
                return 1
            father, mother, ref, husb, wife, note, stamp = row
            print(f"F{fid}  father {label(names, father)}  mother {label(names, mother)}"
                  f"  (ChildID {ref}, HusbOrder {husb}, WifeOrder {wife})")
            if note:
                print(f"   Note: {note!r}")
            for child, order in conn.execute("SELECT ChildID, ChildOrder FROM ChildTable WHERE FamilyID = ?"
                                             " ORDER BY ChildOrder, RecID", (fid,)):
                print(f"   child {order}: {label(names, child)}")
            counts = {k: n for k, sql in USES.items() if (n := conn.execute(sql, (fid,)).fetchone()[0])}
            if counts:
                print("   uses: " + ", ".join(f"{k} {n}" for k, n in counts.items()))
            print(f"   UTCModDate: {stamp}")
    finally:
        conn.close()
    return 0


def create(path: Path, args) -> int:
    problems = []
    sets = parse_assignments(args.set, "--set", problems)
    problems += [f"--set {c!r} is not Note" for c in sets if c != "Note"]
    if not (args.father or args.mother):
        problems.append("give --father or --mother")
    conn = connect_readonly(path)
    try:
        names = person_names(conn)
        for pid in (args.father, args.mother, *args.child):
            if pid and pid not in names:
                problems.append(f"P{pid} not found")
        problems += [f"P{c} is also a partner of the family" for c in args.child if c in (args.father, args.mother)]
        if args.father and args.mother:
            same = conn.execute("SELECT FamilyID FROM FamilyTable WHERE FatherID = ? AND MotherID = ?",
                                (args.father, args.mother)).fetchone()
            if same:
                problems.append(f"F{same[0]} already has this father and mother")
    finally:
        conn.close()
    print(f"New family: father {label(names, args.father)}, mother {label(names, args.mother)}")
    for order, child in enumerate(args.child, 1):
        print(f"   child {order}: {label(names, child)}")
    if "Note" in sets:
        print(f"   Note: {sets['Note']!r}")
    done = stop_unless_applying(problems, args.apply)
    if done is not None:
        return done

    stamp = utc_mod_date()

    def write(conn) -> int:
        fam = conn.execute(
            "INSERT INTO FamilyTable (FatherID, MotherID, ChildID, HusbOrder, WifeOrder, IsPrivate, Proof,"
            " SpouseLabel, FatherLabel, MotherLabel, SpouseLabelStr, FatherLabelStr, MotherLabelStr, Note,"
            " UTCModDate) VALUES (?, ?, 0, 0, 0, 0, 0, 0, 0, 0, '', '', '', ?, ?)",
            (args.father, args.mother, sets.get("Note", ""), stamp)).lastrowid
        for pid in (args.father, args.mother):
            join_spouse(conn, pid, fam, stamp)
        for child in args.child:
            add_child(conn, child, fam, stamp)
        return fam

    print(f"Applied: family F{write_changes(path, write)}.")
    return 0


def edit(path: Path, args) -> int:
    problems = []
    sets = parse_assignments(args.set, "--set", problems)
    problems += [f"--set {c!r} is not Note" for c in sets if c != "Note"]
    if not (args.father is not None or args.mother is not None or args.add_child or args.remove_child or sets):
        problems.append("nothing to change")
    conn = connect_readonly(path)
    try:
        names = person_names(conn)
        row = conn.execute("SELECT FatherID, MotherID, Note FROM FamilyTable WHERE FamilyID = ?",
                           (args.id,)).fetchone()
        if row is None:
            print(f"F{args.id} not found")
            return 1
        father = row[0] if args.father is None else args.father
        mother = row[1] if args.mother is None else args.mother
        members = {r[0] for r in conn.execute("SELECT ChildID FROM ChildTable WHERE FamilyID = ?", (args.id,))}
        for pid in (args.father, args.mother, *args.add_child):
            if pid and pid not in names:
                problems.append(f"P{pid} not found")
        if not (father or mother):
            problems.append("the family would have no father and no mother")
        if father and mother:
            same = conn.execute("SELECT FamilyID FROM FamilyTable WHERE FatherID = ? AND MotherID = ?"
                                " AND FamilyID <> ?", (father, mother, args.id)).fetchone()
            if same:
                problems.append(f"F{same[0]} already has this father and mother")
        for child in args.add_child:
            if child in members:
                problems.append(f"P{child} is already a child of F{args.id}")
            if child in (father, mother):
                problems.append(f"P{child} is also a partner of the family")
        problems += [f"P{c} is not a child of F{args.id}" for c in args.remove_child if c not in members]
    finally:
        conn.close()
    print(f"F{args.id}:")
    if father != row[0]:
        print(f"   father: {label(names, row[0])} -> {label(names, father)}")
    if mother != row[1]:
        print(f"   mother: {label(names, row[1])} -> {label(names, mother)}")
    for child in args.add_child:
        print(f"   add child {label(names, child)}")
    for child in args.remove_child:
        print(f"   remove child {label(names, child)}")
    if "Note" in sets:
        print(f"   Note: {row[2]!r} -> {sets['Note']!r}")
    done = stop_unless_applying(problems, args.apply)
    if done is not None:
        return done

    stamp = utc_mod_date()

    def write(conn) -> None:
        conn.execute("UPDATE FamilyTable SET FatherID = ?, MotherID = ?, Note = ?, UTCModDate = ? WHERE FamilyID = ?",
                     (father, mother, sets.get("Note", row[2]), stamp, args.id))
        for old, new in ((row[0], father), (row[1], mother)):
            if old != new:
                if old:
                    move_spouse(conn, old, args.id, stamp)
                join_spouse(conn, new, args.id, stamp)
        for child in args.remove_child:
            conn.execute("DELETE FROM ChildTable WHERE FamilyID = ? AND ChildID = ?", (args.id, child))
            conn.execute("UPDATE FamilyTable SET ChildID = 0 WHERE FamilyID = ? AND ChildID = ?", (args.id, child))
            move_parent(conn, child, args.id, stamp)
        for child in args.add_child:
            add_child(conn, child, args.id, stamp)

    write_changes(path, write)
    print(f"Applied: family F{args.id} changed.")
    return 0


def delete(path: Path, args) -> int:
    conn = connect_readonly(path)
    try:
        names = person_names(conn)
        row = conn.execute("SELECT FatherID, MotherID FROM FamilyTable WHERE FamilyID = ?", (args.id,)).fetchone()
        if row is None:
            print(f"F{args.id} not found")
            return 1
        children = [r[0] for r in conn.execute("SELECT ChildID FROM ChildTable WHERE FamilyID = ?", (args.id,))]
        used = {k: n for k, sql in USES.items() if (n := conn.execute(sql, (args.id,)).fetchone()[0])}
    finally:
        conn.close()
    print(f"Delete family F{args.id}: father {label(names, row[0])}, mother {label(names, row[1])},"
          f" {len(children)} children (the people are kept)")
    done = stop_unless_applying([f"still used: {used}"] if used else [], args.apply)
    if done is not None:
        return done

    stamp = utc_mod_date()

    def write(conn) -> None:
        conn.execute("DELETE FROM ChildTable WHERE FamilyID = ?", (args.id,))
        conn.execute("DELETE FROM FamilyTable WHERE FamilyID = ?", (args.id,))
        for pid in filter(None, row):
            move_spouse(conn, pid, args.id, stamp)
        for pid in children:
            move_parent(conn, pid, args.id, stamp)

    write_changes(path, write)
    print(f"Applied: family F{args.id} deleted.")
    return 0


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="family.py PATH_TO_RMTREE")
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("get")
    p.add_argument("ids", nargs="*", type=int)
    p.add_argument("--person", type=int)
    p.set_defaults(run=get)

    p = commands.add_parser("create")
    p.add_argument("--father", type=int, default=0)
    p.add_argument("--mother", type=int, default=0)
    p.add_argument("--child", type=int, action="append", default=[])
    p.add_argument("--set", action="append", default=[])
    p.set_defaults(run=create)

    p = commands.add_parser("edit")
    p.add_argument("id", type=int)
    p.add_argument("--father", type=int)
    p.add_argument("--mother", type=int)
    p.add_argument("--add-child", type=int, action="append", default=[])
    p.add_argument("--remove-child", type=int, action="append", default=[])
    p.add_argument("--set", action="append", default=[])
    p.set_defaults(run=edit)

    p = commands.add_parser("delete")
    p.add_argument("id", type=int)
    p.set_defaults(run=delete)

    for name in ("create", "edit", "delete"):
        commands.choices[name].add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])
    if args.command == "get" and not args.ids and args.person is None:
        parser.error("get needs family IDs or --person")
    return args.run(path, args)


if __name__ == "__main__":
    sys.exit(main())
