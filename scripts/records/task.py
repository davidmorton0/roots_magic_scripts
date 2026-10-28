"""Get, create, edit or delete tasks (TaskTable) and their links to people (TaskLinkTable).

  get     ID [ID ...] | --person ID | --name TEXT     Print tasks with their links (read-only).
  create  --name NAME [--details TEXT] [--priority N] [--status N] [--person ID ...]
          [--set COLUMN=VALUE ...]
  edit    ID [--name NAME] [--details TEXT] [--priority N] [--status N] [--set COLUMN=VALUE ...]
          [--link-person ID ...] [--unlink-person ID ...]
  delete  ID

--set sets RefNumber, Filename or Results. Priority 4 is RootsMagic 12's default and 6 is "Low"
(set by hand, 2026-10-15); Status 0 is a new task. New rows copy a task made by hand: TaskType 0, no
dates ("." with SortDate -1), Exclude 0; links use OwnerType 0 (person), the only kind confirmed.
Delete removes the task and its links.

Refused when another task has the name (any case), a person or task does not exist, or a link exists
already (or does not, for --unlink-person).

Name is in an RMNOCASE index: run RootsMagic's rebuild indexes after create or edit.

create, edit and delete are dry runs by default: they print what would change. --apply writes it in
one transaction. RootsMagic must be closed, and the file must be a working copy.

Usage: python task.py PATH_TO_RMTREE get|create|edit|delete ... [--apply]
"""

import argparse
import sys
from pathlib import Path

from rmutils import (
    NO_DATE,
    connect_readonly,
    db_path_arg,
    parse_assignments,
    person_names,
    stop_unless_applying,
    utc_mod_date,
    write_changes,
)

OWNER_PERSON = 0
TASK_TYPE, STATUS, PRIORITY = 0, 0, 4
NO_SORT = -1
SET_COLUMNS = ("RefNumber", "Filename", "Results")


def check_sets(sets: dict[str, str], problems: list[str]) -> None:
    for column in [c for c in sets if c not in SET_COLUMNS]:
        problems.append(f"--set {column!r} is not one of {', '.join(SET_COLUMNS)}")
        del sets[column]


def get(path: Path, args) -> int:
    conn = connect_readonly(path)
    try:
        names = person_names(conn)
        if args.ids:
            ids = args.ids
        elif args.person is not None:
            ids = [r[0] for r in conn.execute("SELECT TaskID FROM TaskLinkTable WHERE OwnerType = ? AND OwnerID = ?"
                                              " ORDER BY TaskID", (OWNER_PERSON, args.person))]
        else:
            ids = [r[0] for r in conn.execute("SELECT TaskID FROM TaskTable WHERE Name LIKE ? ORDER BY TaskID",
                                              (f"%{args.name}%",))]
        if not ids:
            print("No tasks found")
            return 1
        for tid in ids:
            row = conn.execute("SELECT Name, Status, Priority, RefNumber, Filename, Details, Results, UTCModDate"
                               " FROM TaskTable WHERE TaskID = ?", (tid,)).fetchone()
            if row is None:
                print(f"T{tid} not found")
                return 1
            name, status, priority, ref, filename, details, results, stamp = row
            print(f"T{tid}  '{name}'  (Status {status}, Priority {priority})")
            for label, value in (("RefNumber", ref), ("Filename", filename), ("Results", results)):
                if value:
                    print(f"   {label}: {value!r}")
            for line in (details or "").splitlines():
                print(f"   | {line}")
            for owner_type, owner in conn.execute("SELECT OwnerType, OwnerID FROM TaskLinkTable WHERE TaskID = ?"
                                                  " ORDER BY LinkID", (tid,)):
                who = f"P{owner} {names.get(owner, '(not found)')}" if owner_type == OWNER_PERSON \
                    else f"owner type {owner_type} ID {owner}"
                print(f"   link -> {who}")
            print(f"   UTCModDate: {stamp}")
    finally:
        conn.close()
    return 0


def create(path: Path, args) -> int:
    problems = []
    sets = parse_assignments(args.set, "--set", problems)
    check_sets(sets, problems)
    conn = connect_readonly(path)
    try:
        names = person_names(conn)
        problems += [f"P{p} not found" for p in args.person if p not in names]
        clash = conn.execute("SELECT TaskID FROM TaskTable WHERE Name = ? COLLATE NOCASE", (args.name,)).fetchone()
        if clash:
            problems.append(f"T{clash[0]} already has the name {args.name!r}")
    finally:
        conn.close()
    print(f"New task '{args.name}' (Status {args.status}, Priority {args.priority})")
    for line in args.details.splitlines():
        print(f"   | {line}")
    for column, value in sets.items():
        print(f"   {column}: {value!r}")
    for pid in args.person:
        print(f"   link -> P{pid} {names.get(pid, '(not found)')}")
    done = stop_unless_applying(problems, args.apply)
    if done is not None:
        return done

    stamp = utc_mod_date()

    def write(conn) -> int:
        tid = conn.execute(
            "INSERT INTO TaskTable (TaskType, RefNumber, Name, Status, Priority, Date1, Date2, Date3, SortDate1,"
            " SortDate2, SortDate3, Filename, Details, Results, UTCModDate, Exclude)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
            (TASK_TYPE, sets.get("RefNumber", ""), args.name, args.status, args.priority, NO_DATE, NO_DATE, NO_DATE,
             NO_SORT, NO_SORT, NO_SORT, sets.get("Filename", ""), args.details, sets.get("Results", ""),
             stamp)).lastrowid
        for pid in args.person:
            conn.execute("INSERT INTO TaskLinkTable (TaskID, OwnerType, OwnerID, UTCModDate) VALUES (?, ?, ?, ?)",
                         (tid, OWNER_PERSON, pid, stamp))
        return tid

    print(f"Applied: task T{write_changes(path, write)}. Run RootsMagic's rebuild indexes.")
    return 0


def edit(path: Path, args) -> int:
    problems = []
    changes = dict(parse_assignments(args.set, "--set", problems))
    check_sets(changes, problems)
    for option, column in (("name", "Name"), ("details", "Details"), ("priority", "Priority"),
                           ("status", "Status")):
        if getattr(args, option) is not None:
            changes[column] = getattr(args, option)
    if not (changes or args.link_person or args.unlink_person):
        problems.append("nothing to change")
    conn = connect_readonly(path)
    try:
        names = person_names(conn)
        columns = list(changes) or ["Name"]
        row = conn.execute("SELECT Name, " + ", ".join(columns) + " FROM TaskTable WHERE TaskID = ?",
                           (args.id,)).fetchone()
        if row is None:
            print(f"T{args.id} not found")
            return 1
        task_name, old = row[0], dict(zip(columns, row[1:]))
        if args.name is not None:
            clash = conn.execute("SELECT TaskID FROM TaskTable WHERE Name = ? COLLATE NOCASE AND TaskID <> ?",
                                 (args.name, args.id)).fetchone()
            if clash:
                problems.append(f"T{clash[0]} already has the name {args.name!r}")
        linked = {r[0] for r in conn.execute("SELECT OwnerID FROM TaskLinkTable WHERE TaskID = ? AND OwnerType = ?",
                                             (args.id, OWNER_PERSON))}
        for pid in args.link_person:
            if pid not in names:
                problems.append(f"P{pid} not found")
            elif pid in linked:
                problems.append(f"T{args.id} is already linked to P{pid}")
        problems += [f"T{args.id} is not linked to P{p}" for p in args.unlink_person if p not in linked]
    finally:
        conn.close()
    print(f"T{args.id} '{task_name}':")
    for column, value in changes.items():
        print(f"   {column}: {old[column]!r} -> {value!r}")
    for pid in args.link_person:
        print(f"   link -> P{pid} {names.get(pid, '(not found)')}")
    for pid in args.unlink_person:
        print(f"   unlink from P{pid} {names.get(pid, '(not found)')}")
    done = stop_unless_applying(problems, args.apply)
    if done is not None:
        return done

    stamp = utc_mod_date()

    def write(conn) -> None:
        assignments = {**changes, "UTCModDate": stamp}
        conn.execute("UPDATE TaskTable SET " + ", ".join(f"{c} = ?" for c in assignments) + " WHERE TaskID = ?",
                     [*assignments.values(), args.id])
        for pid in args.unlink_person:
            conn.execute("DELETE FROM TaskLinkTable WHERE TaskID = ? AND OwnerType = ? AND OwnerID = ?",
                         (args.id, OWNER_PERSON, pid))
        for pid in args.link_person:
            conn.execute("INSERT INTO TaskLinkTable (TaskID, OwnerType, OwnerID, UTCModDate) VALUES (?, ?, ?, ?)",
                         (args.id, OWNER_PERSON, pid, stamp))

    write_changes(path, write)
    print(f"Applied: task T{args.id} changed. Run RootsMagic's rebuild indexes.")
    return 0


def delete(path: Path, args) -> int:
    conn = connect_readonly(path)
    try:
        row = conn.execute("SELECT Name FROM TaskTable WHERE TaskID = ?", (args.id,)).fetchone()
        links = conn.execute("SELECT COUNT(*) FROM TaskLinkTable WHERE TaskID = ?", (args.id,)).fetchone()[0]
    finally:
        conn.close()
    if row is None:
        print(f"T{args.id} not found")
        return 1
    print(f"Delete task T{args.id} '{row[0]}' and its {links} links")
    done = stop_unless_applying([], args.apply)
    if done is not None:
        return done

    def write(conn) -> None:
        conn.execute("DELETE FROM TaskLinkTable WHERE TaskID = ?", (args.id,))
        conn.execute("DELETE FROM TaskTable WHERE TaskID = ?", (args.id,))

    write_changes(path, write)
    print(f"Applied: task T{args.id} deleted.")
    return 0


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="task.py PATH_TO_RMTREE")
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("get")
    p.add_argument("ids", nargs="*", type=int)
    p.add_argument("--person", type=int)
    p.add_argument("--name")
    p.set_defaults(run=get)

    p = commands.add_parser("create")
    p.add_argument("--name", required=True)
    p.add_argument("--details", default="")
    p.add_argument("--priority", type=int, default=PRIORITY)
    p.add_argument("--status", type=int, default=STATUS)
    p.add_argument("--person", type=int, action="append", default=[])
    p.set_defaults(run=create)

    p = commands.add_parser("edit")
    p.add_argument("id", type=int)
    p.add_argument("--name")
    p.add_argument("--details")
    p.add_argument("--priority", type=int)
    p.add_argument("--status", type=int)
    p.add_argument("--link-person", type=int, action="append", default=[])
    p.add_argument("--unlink-person", type=int, action="append", default=[])
    p.set_defaults(run=edit)

    p = commands.add_parser("delete")
    p.add_argument("id", type=int)
    p.set_defaults(run=delete)

    for name in ("create", "edit"):
        commands.choices[name].add_argument("--set", action="append", default=[])
    for name in ("create", "edit", "delete"):
        commands.choices[name].add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])
    if args.command == "get" and not args.ids and args.person is None and args.name is None:
        parser.error("get needs task IDs, --person or --name")
    return args.run(path, args)


if __name__ == "__main__":
    sys.exit(main())
