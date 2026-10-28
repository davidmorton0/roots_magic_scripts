"""Validate tasks (TaskTable, TaskLinkTable). Read-only.

Task links use OwnerType 0 (person), the only kind confirmed; links to other owner types are
reported as not checked, not as errors.

Writes each task with an issue to tmp/output/validate/<timestamp>_validate_task.txt and prints a
summary of counts.

Usage: python validate_task.py PATH_TO_RMTREE [--config FILE]
"""

import sys

from validate_common import OWNER_PERSON, Checks, Tree, date_problem, run

CHECKS = Checks()


def tasks(t: Tree) -> dict[int, str]:
    return dict(t.conn.execute("SELECT TaskID, Name FROM TaskTable"))


@CHECKS.add("task_unlinked", "Tasks linked to nothing")
def task_unlinked(t: Tree) -> list[str]:
    linked = {r[0] for r in t.conn.execute("SELECT TaskID FROM TaskLinkTable")}
    return [f"{name} [T{tid}]" for tid, name in sorted(tasks(t).items()) if tid not in linked]


@CHECKS.add("task_link_orphan", "Task links whose task or person is missing")
def task_link_orphan(t: Tree) -> list[str]:
    names = tasks(t)
    out = []
    for link, tid, otype, oid in t.conn.execute(
            "SELECT LinkID, TaskID, OwnerType, OwnerID FROM TaskLinkTable ORDER BY LinkID"):
        if tid not in names:
            out.append(f"link {link}: task T{tid} missing")
        elif otype == OWNER_PERSON and oid not in t.names:
            out.append(f"link {link}: {names[tid]} [T{tid}] -> person P{oid} missing")
        elif otype != OWNER_PERSON:
            out.append(f"link {link}: {names[tid]} [T{tid}] -> owner type {otype} id {oid} not checked")
    return out


@CHECKS.add("task_date_form", "Task dates that are not a well-formed encoded date")
def task_date_form(t: Tree) -> list[str]:
    return [
        f"{name} [T{tid}] Date{n} {date!r}: {problem}"
        for tid, name, *dates in t.conn.execute("SELECT TaskID, Name, Date1, Date2, Date3 FROM TaskTable ORDER BY 1")
        for n, date in enumerate(dates, 1)
        if (problem := date_problem(date))
    ]


def main() -> int:
    return run(__doc__, "task", CHECKS)


if __name__ == "__main__":
    sys.exit(main())
