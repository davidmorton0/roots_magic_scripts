"""Change a person's primary name: given names, surname, or both.

Updates the primary NameTable row. GivenMP and SurnameMP (filled on rows RootsMagic 12
made, empty on older ones) follow when they held the old value. Surname and Given are in
RMNOCASE indexes: run RootsMagic's rebuild indexes after.

Dry run by default. --apply writes it in one transaction. RootsMagic must be closed, and
the file must be a working copy.

Usage: python rename_person.py PATH_TO_RMTREE --person ID [--given GIVEN] [--surname SURNAME]
           [--apply]
"""

import argparse
import sys

from rmutils import connect_readonly, connect_readwrite, db_path_arg, utc_mod_date


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="rename_person.py PATH_TO_RMTREE")
    parser.add_argument("--person", type=int, required=True)
    parser.add_argument("--given")
    parser.add_argument("--surname")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(sys.argv[2:])
    if args.given is None and args.surname is None:
        print("Not changed: give --given, --surname or both")
        return 2

    conn = connect_readonly(path)
    try:
        row = conn.execute("SELECT NameID, Given, Surname, GivenMP, SurnameMP FROM NameTable"
                           " WHERE OwnerID = ? AND IsPrimary = 1", (args.person,)).fetchone()
    finally:
        conn.close()
    if row is None:
        print(f"Not changed: P{args.person} has no primary name")
        return 1
    name_id, given, surname, given_mp, surname_mp = row
    new_given = given if args.given is None else args.given
    new_surname = surname if args.surname is None else args.surname
    new_given_mp = new_given if given_mp == given else given_mp
    new_surname_mp = new_surname if surname_mp == surname else surname_mp
    print(f"P{args.person}: {given} {surname} -> {new_given} {new_surname}")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0
    conn = connect_readwrite(path)
    try:
        conn.execute("UPDATE NameTable SET Given = ?, Surname = ?, GivenMP = ?, SurnameMP = ?, UTCModDate = ?"
                     " WHERE NameID = ?", (new_given, new_surname, new_given_mp, new_surname_mp, utc_mod_date(),
                                           name_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print("Applied. Run RootsMagic's rebuild indexes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
