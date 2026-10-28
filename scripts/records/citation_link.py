"""Get, create, edit or delete citation links (CitationLinkTable): a citation cited on a person,
family, event or name.

  get     LINK_ID [LINK_ID ...] | --citation ID | --owner KIND:ID   Print links (read-only).
  create  --citation ID --owner KIND:ID --quality XYZ [--sort-order N]
  edit    LINK_ID [LINK_ID ...] [--quality XYZ] [--sort-order N] [--private 0|1]
  delete  LINK_ID [LINK_ID ...]

KIND is person, family, event or name (OwnerType 0, 1, 2, 7; the ID is a PersonID, FamilyID,
EventID or NameID). Quality is three characters, as RootsMagic 12 writes them: information P/S/~,
evidence D/I/N/~, source O/X/~ ("~~~" not assessed). New links have IsPrivate 0 and Flags 0.

Refused when the citation or owner does not exist, the owner already has the citation (create), a
link does not exist, or a quality is not valid.

create, edit and delete are dry runs by default: they print what would change. --apply writes it in
one transaction. RootsMagic must be closed, and the file must be a working copy.

Usage: python citation_link.py PATH_TO_RMTREE get|create|edit|delete ... [--apply]
"""

import argparse
import re
import sys
from pathlib import Path

from rmutils import OWNER_TYPES, connect_readonly, db_path_arg, utc_mod_date, write_changes

QUALITY = re.compile(r"[PS~][DIN~][OX~]")
KIND_OF_CODE = {code: kind for kind, (code, _, _) in OWNER_TYPES.items()}


def parse_owner(text: str, problems: list[str]) -> tuple[str, int] | None:
    kind, _, owner = text.partition(":")
    if kind not in OWNER_TYPES or not owner.isdigit():
        problems.append(f"--owner {text!r} is not KIND:ID (kind {', '.join(OWNER_TYPES)})")
        return None
    return kind, int(owner)


def describe(row) -> str:
    link, citation, owner_type, owner, order, quality, private, flags = row
    kind = KIND_OF_CODE.get(owner_type, f"type {owner_type}")
    return (f"L{link}: C{citation} -> {kind} {owner} {quality} (SortOrder {order}, IsPrivate {private},"
            f" Flags {flags})")


COLUMNS = "LinkID, CitationID, OwnerType, OwnerID, SortOrder, Quality, IsPrivate, Flags"


def fetch_links(conn, ids: list[int]) -> tuple[list[tuple], list[int]]:
    rows = [conn.execute(f"SELECT {COLUMNS} FROM CitationLinkTable WHERE LinkID = ?", (i,)).fetchone()
            for i in ids]
    return [r for r in rows if r], [i for i, r in zip(ids, rows) if r is None]


def get(path: Path, args) -> int:
    conn = connect_readonly(path)
    try:
        if args.ids:
            rows, missing = fetch_links(conn, args.ids)
            if missing:
                print("Links not found: " + ", ".join(f"L{i}" for i in missing))
                return 1
        elif args.citation is not None:
            rows = conn.execute(f"SELECT {COLUMNS} FROM CitationLinkTable WHERE CitationID = ? ORDER BY LinkID",
                                (args.citation,)).fetchall()
        else:
            problems = []
            owner = parse_owner(args.owner, problems)
            if problems:
                print(problems[0])
                return 1
            rows = conn.execute(f"SELECT {COLUMNS} FROM CitationLinkTable WHERE OwnerType = ? AND OwnerID = ?"
                                " ORDER BY LinkID", (OWNER_TYPES[owner[0]][0], owner[1])).fetchall()
    finally:
        conn.close()
    for row in rows:
        print(describe(row))
    if not rows:
        print("No links found")
        return 1
    return 0


def create(path: Path, args) -> int:
    problems = []
    owner = parse_owner(args.owner, problems)
    if not QUALITY.fullmatch(args.quality):
        problems.append(f"quality {args.quality!r} is not three characters P/S/~, D/I/N/~, O/X/~")
    conn = connect_readonly(path)
    try:
        if not conn.execute("SELECT 1 FROM CitationTable WHERE CitationID = ?", (args.citation,)).fetchone():
            problems.append(f"C{args.citation} not found")
        if owner:
            code, table, key = OWNER_TYPES[owner[0]]
            if not conn.execute(f"SELECT 1 FROM {table} WHERE {key} = ?", (owner[1],)).fetchone():
                problems.append(f"{owner[0]} {owner[1]} not found")
            elif conn.execute("SELECT 1 FROM CitationLinkTable WHERE CitationID = ? AND OwnerType = ?"
                              " AND OwnerID = ?", (args.citation, code, owner[1])).fetchone():
                problems.append(f"{owner[0]} {owner[1]} already has C{args.citation}")
    finally:
        conn.close()
    print(f"New link: C{args.citation} -> {args.owner} {args.quality} (SortOrder {args.sort_order})")
    if problems:
        print("Refused:\n   " + "\n   ".join(problems))
        return 1
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    def write(conn) -> int:
        return conn.execute(
            "INSERT INTO CitationLinkTable (CitationID, OwnerType, OwnerID, SortOrder, Quality, IsPrivate, Flags,"
            " UTCModDate) VALUES (?, ?, ?, ?, ?, 0, 0, ?)",
            (args.citation, OWNER_TYPES[owner[0]][0], owner[1], args.sort_order, args.quality,
             utc_mod_date())).lastrowid

    print(f"Applied: link L{write_changes(path, write)}.")
    return 0


def edit(path: Path, args) -> int:
    problems = []
    changes = {}
    if args.quality is not None:
        if not QUALITY.fullmatch(args.quality):
            problems.append(f"quality {args.quality!r} is not three characters P/S/~, D/I/N/~, O/X/~")
        changes["Quality"] = args.quality
    if args.sort_order is not None:
        changes["SortOrder"] = args.sort_order
    if args.private is not None:
        changes["IsPrivate"] = args.private
    if not changes:
        problems.append("nothing to change: give --quality, --sort-order or --private")
    conn = connect_readonly(path)
    try:
        rows, missing = fetch_links(conn, args.ids)
    finally:
        conn.close()
    problems += [f"L{i} not found" for i in missing]
    for row in rows:
        print(describe(row))
    print("   -> " + ", ".join(f"{c} {v}" for c, v in changes.items()))
    if problems:
        print("Refused:\n   " + "\n   ".join(problems))
        return 1
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()

    def write(conn) -> None:
        for link in args.ids:
            conn.execute("UPDATE CitationLinkTable SET " + ", ".join(f"{c} = ?" for c in changes)
                         + ", UTCModDate = ? WHERE LinkID = ?", [*changes.values(), stamp, link])

    write_changes(path, write)
    print(f"Applied: {len(args.ids)} links changed.")
    return 0


def delete(path: Path, args) -> int:
    conn = connect_readonly(path)
    try:
        rows, missing = fetch_links(conn, args.ids)
    finally:
        conn.close()
    for row in rows:
        print("Delete " + describe(row))
    if missing:
        print("Refused: " + ", ".join(f"L{i}" for i in missing) + " not found")
        return 1
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    def write(conn) -> None:
        for link in args.ids:
            conn.execute("DELETE FROM CitationLinkTable WHERE LinkID = ?", (link,))

    write_changes(path, write)
    print(f"Applied: {len(args.ids)} links deleted.")
    return 0


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="citation_link.py PATH_TO_RMTREE")
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("get")
    p.add_argument("ids", nargs="*", type=int)
    p.add_argument("--citation", type=int)
    p.add_argument("--owner")
    p.set_defaults(run=get)

    p = commands.add_parser("create")
    p.add_argument("--citation", type=int, required=True)
    p.add_argument("--owner", required=True)
    p.add_argument("--quality", required=True)
    p.add_argument("--sort-order", type=int, default=0)
    p.set_defaults(run=create)

    p = commands.add_parser("edit")
    p.add_argument("ids", nargs="+", type=int)
    p.add_argument("--quality")
    p.add_argument("--sort-order", type=int)
    p.add_argument("--private", type=int, choices=(0, 1))
    p.set_defaults(run=edit)

    p = commands.add_parser("delete")
    p.add_argument("ids", nargs="+", type=int)
    p.set_defaults(run=delete)

    for name in ("create", "edit", "delete"):
        commands.choices[name].add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])
    if args.command == "get" and not (args.ids or args.citation is not None or args.owner):
        parser.error("get needs link IDs, --citation or --owner")
    return args.run(path, args)


if __name__ == "__main__":
    sys.exit(main())
