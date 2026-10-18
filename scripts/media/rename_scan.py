"""Rename scan files on the Windows drive and in the media rows that use them.

For each --rename OLD NEW (OLD a full Windows path, NEW a file name in the
same folder): every MultimediaTable row with that folder (MediaPath) and file
(MediaFile) gets MediaFile = NEW, and the file itself is renamed. Refused if
OLD does not exist, NEW already exists, or no media row uses OLD.

MediaFile is in an RMNOCASE index: run RootsMagic's rebuild indexes after.

Dry run by default: prints what would change. --apply updates the rows in one
transaction, renames the files, then commits; if a rename fails, the files
already renamed are renamed back and nothing is committed. RootsMagic must be
closed, and the file must be a working copy.

Usage: python rename_scan.py PATH_TO_RMTREE --rename OLD_PATH NEW_NAME
           [--rename OLD_PATH NEW_NAME ...] [--apply]
"""

import argparse
import sys

from rmutils import (
    connect_readonly,
    connect_readwrite,
    db_path_arg,
    rename_windows_file,
    utc_mod_date,
    windows_file_modified,
)


def split_path(path: str) -> tuple[str, str]:
    folder, _, name = path.rpartition("\\")
    return folder, name


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="rename_scan.py PATH_TO_RMTREE")
    parser.add_argument("--rename", nargs=2, action="append", required=True,
                        metavar=("OLD_PATH", "NEW_NAME"))
    parser.add_argument("--apply", action="store_true", help="rename the files and rows")
    args = parser.parse_args(sys.argv[2:])

    conn = connect_readonly(path)
    try:
        plans, problems = [], []
        for old, new in args.rename:
            folder, name = split_path(old)
            rows = [mid for (mid,) in conn.execute(
                "SELECT MediaID FROM MultimediaTable"
                " WHERE lower(MediaPath) = lower(?) AND lower(MediaFile) = lower(?)",
                (folder, name),
            )]
            if "\\" in new or not new:
                problems.append(f"{new!r} is not a plain file name")
            elif not rows:
                problems.append(f"no media row uses {old}")
            elif windows_file_modified(old) is None:
                problems.append(f"file not found: {old}")
            elif windows_file_modified(f"{folder}\\{new}") is not None:
                problems.append(f"already exists: {folder}\\{new}")
            plans.append((old, folder, name, new, rows))
    finally:
        conn.close()

    for old, folder, name, new, rows in plans:
        print(f"{old} -> {new} (media {', '.join(f'M{m}' for m in rows) or 'none'})")
    if problems:
        print("Not applied:")
        for p in problems:
            print(f"   {p}")
        return 1
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    renamed = []
    try:
        for old, folder, name, new, rows in plans:
            for mid in rows:
                cur = conn.execute(
                    "UPDATE MultimediaTable SET MediaFile = ?, UTCModDate = ? WHERE MediaID = ?",
                    (new, stamp, mid),
                )
                if cur.rowcount != 1:
                    raise RuntimeError(f"media M{mid} not updated")
            rename_windows_file(old, new)
            renamed.append((f"{folder}\\{new}", name))
        conn.commit()
    except Exception:
        conn.rollback()
        for current, original in reversed(renamed):
            rename_windows_file(current, original)
        raise
    finally:
        conn.close()
    print(f"Applied: {len(plans)} files and {sum(len(p[4]) for p in plans)} media rows renamed."
          " Run RootsMagic's rebuild indexes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
