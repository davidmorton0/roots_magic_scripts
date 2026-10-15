"""Rename a source.

Refuses if another source already has the new name (compared without regard
to case). Only SourceTable.Name changes; RootsMagic's source-name index uses
RMNOCASE, so run Rebuild Indexes in RootsMagic afterwards.

Dry run by default: prints the change. --apply writes it. RootsMagic must be
closed, and the file must be a working copy.

Usage: python rename_source.py PATH_TO_RMTREE SOURCE_ID NEW_NAME [--apply]
"""

import argparse
import sys

from rmutils import connect_readonly, connect_readwrite, db_path_arg, utc_mod_date


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="rename_source.py PATH_TO_RMTREE")
    parser.add_argument("source", type=int)
    parser.add_argument("name")
    parser.add_argument("--apply", action="store_true", help="write the change")
    args = parser.parse_args(sys.argv[2:])

    conn = connect_readonly(path)
    try:
        row = conn.execute("SELECT Name FROM SourceTable WHERE SourceID = ?", (args.source,)).fetchone()
        clash = conn.execute(
            "SELECT SourceID FROM SourceTable WHERE Name = ? COLLATE NOCASE AND SourceID <> ?",
            (args.name, args.source),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        print(f"Source S{args.source} not found")
        return 1
    if clash:
        print(f"Source S{clash[0]} is already named '{args.name}'")
        return 1

    print(f"S{args.source}: '{row[0]}' -> '{args.name}'")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0
    conn = connect_readwrite(path)
    try:
        conn.execute(
            "UPDATE SourceTable SET Name = ?, UTCModDate = ? WHERE SourceID = ?",
            (args.name, utc_mod_date(), args.source),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print("Applied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
