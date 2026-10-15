"""List everyone in a RootsMagic .rmtree database.

Opens the file read-only. One line per person: PersonID, Sex code (raw),
primary name, and the BirthYear/DeathYear stored on the name row.
Codes and years are shown as stored; nothing is decoded.
Writes the list to tmp/output/general/<timestamp>_people.txt.

Usage: python people.py PATH_TO_RMTREE
"""

import sys

from rmutils import connect_readonly, db_path_arg, full_name, output_file

QUERY = """
SELECT p.PersonID, p.Sex,
       n.Surname, n.Given, n.Prefix, n.Suffix,
       n.BirthYear, n.DeathYear
FROM PersonTable p
LEFT JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
ORDER BY n.Surname COLLATE RMNOCASE, n.Given COLLATE RMNOCASE, p.PersonID
"""


def year(value) -> str:
    return str(value) if value else ""


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2

    conn = connect_readonly(path)
    try:
        rows = conn.execute(QUERY).fetchall()
    finally:
        conn.close()

    with output_file("people"):
        print(f"{'ID':>5}  {'Sex':>3}  {'Born':>4}  {'Died':>4}  Name")
        for pid, sex, surname, given, prefix, suffix, born, died in rows:
            name = full_name(surname, given, prefix, suffix)
            print(f"{pid:>5}  {sex:>3}  {year(born):>4}  {year(died):>4}  {name}")
        print(f"\n{len(rows)} people")
    print(f"{len(rows)} people")
    return 0


if __name__ == "__main__":
    sys.exit(main())
