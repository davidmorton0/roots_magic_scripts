"""Add an alternative (AKA) name to a person, cited to a citation.

Writes the name as RootsMagic 12 stored one made by hand: NameType 1 (AKA), not primary, no date
(SortDate 9223372036854775807), BirthYear copied from the primary name; GivenMP and SurnameMP filled.
The citation link uses OwnerType 7 (name) and the NameID.

Refused: the person or citation does not exist, or the person already has that name.

Dry run by default: prints the name. --apply writes it in one transaction. RootsMagic must be
closed, and the file must be a working copy.

Usage: python add_alternative_name.py PATH_TO_RMTREE --person ID --given GIVEN --surname SURNAME
           --citation ID --quality XYZ [--apply]
"""

import argparse
import re
import sys

from rmutils import connect_readonly, connect_readwrite, db_path_arg, utc_mod_date

NAME_AKA, OWNER_NAME = 1, 7


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="add_alternative_name.py PATH_TO_RMTREE")
    parser.add_argument("--person", type=int, required=True)
    parser.add_argument("--given", required=True)
    parser.add_argument("--surname", required=True)
    parser.add_argument("--citation", type=int, required=True)
    parser.add_argument("--quality", required=True, help="three characters, e.g. PIX")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(sys.argv[2:])
    if not re.fullmatch(r"[PS~][DIN~][OX~]", args.quality):
        print(f"Quality {args.quality!r} is not three characters P/S/~, D/I/N/~, O/X/~")
        return 1

    conn = connect_readonly(path)
    try:
        names = conn.execute("SELECT Given, Surname, IsPrimary, BirthYear FROM NameTable WHERE OwnerID = ?",
                             (args.person,)).fetchall()
        cited = conn.execute("SELECT 1 FROM CitationTable WHERE CitationID = ?", (args.citation,)).fetchone()
    finally:
        conn.close()
    problems = []
    if not names:
        problems.append(f"P{args.person} not found")
    if not cited:
        problems.append(f"C{args.citation} not found")
    if any(g == args.given and s == args.surname for g, s, _, _ in names):
        problems.append(f"P{args.person} already has the name {args.given} {args.surname}")
    if problems:
        print("Not changed: " + "; ".join(problems))
        return 1
    primary = next((n for n in names if n[2] == 1), names[0])
    print(f"P{args.person} ({primary[0]} {primary[1]}): add alternative name {args.given} {args.surname},"
          f" cited C{args.citation} {args.quality}")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0
    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    try:
        name_id = conn.execute(
            "INSERT INTO NameTable (OwnerID, Surname, Given, Prefix, Suffix, Nickname, NameType, Date, SortDate,"
            " IsPrimary, IsPrivate, Proof, Sentence, Note, BirthYear, DeathYear, Display, Language, UTCModDate,"
            " SurnameMP, GivenMP, NicknameMP) VALUES (?, ?, ?, '', '', '', ?, '.', 9223372036854775807, 0, 0, 0,"
            " '', '', ?, 0, 0, '', ?, ?, ?, '')",
            (args.person, args.surname, args.given, NAME_AKA, primary[3] or 0, stamp, args.surname,
             args.given)).lastrowid
        conn.execute("INSERT INTO CitationLinkTable (CitationID, OwnerType, OwnerID, SortOrder, Quality, IsPrivate, Flags,"
                     " UTCModDate) VALUES (?, ?, ?, 0, ?, 0, 0, ?)",
                     (args.citation, OWNER_NAME, name_id, args.quality, stamp))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"Applied: name N{name_id}. Run RootsMagic's rebuild indexes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
