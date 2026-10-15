"""Create a RootsMagic task (to-do) linked to a person.

Writes the task the way RootsMagic 12 stored one made by hand (2026-10-15):
TaskType 0, Status 0, Priority 4, no dates ("." with SortDate -1, as in the
older tasks), empty RefNumber, Filename and Results, linked to the person
with TaskLinkTable OwnerType 0.

Dry run by default: prints the task. --apply writes it in one transaction.
RootsMagic must be closed, and the file must be a working copy.

Usage: python create_task.py PATH_TO_RMTREE --person ID --name NAME --details TEXT
           [--priority N] [--apply]
"""

import argparse
import sys

from rmutils import connect_readonly, connect_readwrite, db_path_arg, person_names, utc_mod_date

OWNER_PERSON = 0
TASK_TYPE, STATUS, PRIORITY = 0, 0, 4
NO_DATE, NO_SORT = ".", -1


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="create_task.py PATH_TO_RMTREE")
    parser.add_argument("--person", type=int, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--details", required=True)
    parser.add_argument("--priority", type=int, default=PRIORITY,
                        help="RootsMagic priority number (default 4, as on a new task)")
    parser.add_argument("--apply", action="store_true", help="write the task")
    args = parser.parse_args(sys.argv[2:])

    conn = connect_readonly(path)
    try:
        names = person_names(conn)
        duplicate = conn.execute("SELECT TaskID FROM TaskTable WHERE Name = ?", (args.name,)).fetchone()
    finally:
        conn.close()
    if args.person not in names:
        print(f"Person P{args.person} not found")
        return 1
    if duplicate:
        print(f"Task T{duplicate[0]} already has the name '{args.name}'")
        return 1

    print(f"New task, linked to {names[args.person]} [P{args.person}]")
    print(f"   Name: {args.name}")
    print(f"   Priority: {args.priority}")
    print("   Details:")
    for line in args.details.splitlines():
        print(f"      {line}")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    try:
        task_id = conn.execute(
            """INSERT INTO TaskTable (TaskType, RefNumber, Name, Status, Priority, Date1, Date2,
                   Date3, SortDate1, SortDate2, SortDate3, Filename, Details, Results, UTCModDate,
                   Exclude) VALUES (?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, '', ?, 0)""",
            (TASK_TYPE, args.name, STATUS, args.priority, NO_DATE, NO_DATE, NO_DATE,
             NO_SORT, NO_SORT, NO_SORT, args.details, stamp),
        ).lastrowid
        conn.execute(
            "INSERT INTO TaskLinkTable (TaskID, OwnerType, OwnerID, UTCModDate) VALUES (?, ?, ?, ?)",
            (task_id, OWNER_PERSON, args.person, stamp),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"Applied: task T{task_id}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
