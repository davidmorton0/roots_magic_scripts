"""Find people by name (read-only).

Matches any name row, primary or alternative, ignoring case: the surname must match
exactly (or as a SQL LIKE pattern with %), and every given-name word typed must begin one
of the person's given names in order ("Wil" finds William; "John W" finds John William).
One line per person: PersonID, primary name, birth and death years, and the matching
name if it is an alternative one.

Usage: python find_person.py PATH_TO_RMTREE --surname SURNAME [--given GIVEN]
"""

import argparse
import sys

from rmutils import connect_readonly, db_path_arg, person_names


def given_fits(typed: str, given: str) -> bool:
    want, have = typed.casefold().split(), (given or "").casefold().split()
    i = 0
    for word in want:
        while i < len(have) and not have[i].startswith(word):
            i += 1
        if i == len(have):
            return False
        i += 1
    return True


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="find_person.py PATH_TO_RMTREE")
    parser.add_argument("--surname", required=True)
    parser.add_argument("--given", default="")
    args = parser.parse_args(sys.argv[2:])

    conn = connect_readonly(path)
    try:
        names = person_names(conn)
        rows = conn.execute(
            "SELECT OwnerID, Given, Surname, IsPrimary, BirthYear, DeathYear FROM NameTable"
            " WHERE Surname LIKE ? ORDER BY OwnerID, IsPrimary DESC", (args.surname,)).fetchall()
        years = {pid: (born, died) for pid, born, died in conn.execute(
            "SELECT OwnerID, BirthYear, DeathYear FROM NameTable WHERE IsPrimary = 1")}
    finally:
        conn.close()
    found = {}
    for pid, given, surname, primary, _, _ in rows:
        if pid not in found and given_fits(args.given, given):
            found[pid] = "" if primary else f" (as {given} {surname})"
    for pid, alias in found.items():
        born, died = years.get(pid, (0, 0))
        print(f"P{pid} {names.get(pid, '')}, {born or '?'}-{died or '?'}{alias}")
    print(f"{len(found)} found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
