"""Rename or move scan files on the Windows drive and in the media rows that use them.

For each --rename OLD NEW (OLD a full Windows path; NEW a file name in the same
folder, or a full Windows path to move the file to another folder, created if
missing): every MultimediaTable row with that folder (MediaPath) and file
(MediaFile) gets the new folder and file name, and the file itself is renamed or
moved. Refused if OLD does not exist, NEW already exists, or no media row uses OLD.

MediaPath and MediaFile are in RMNOCASE indexes: run RootsMagic's rebuild indexes after.

Dry run by default: prints what would change. --apply updates the rows in one
transaction, renames or moves the files, then commits; if one fails, the files
already done are put back and nothing is committed. RootsMagic must be closed,
and the file must be a working copy.

Usage: python rename_scan.py PATH_TO_RMTREE --rename OLD_PATH NEW_NAME_OR_PATH
           [--rename OLD_PATH NEW_NAME_OR_PATH ...] [--apply]
"""

import argparse
import sys

from rmutils import (
    connect_readonly,
    connect_readwrite,
    db_path_arg,
    move_windows_file,
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
            new_folder, new_name = split_path(new) if "\\" in new else (folder, new)
            rows = [mid for (mid,) in conn.execute(
                "SELECT MediaID FROM MultimediaTable"
                " WHERE lower(MediaPath) = lower(?) AND lower(MediaFile) = lower(?)",
                (folder, name),
            )]
            if not new_name or not new_folder:
                problems.append(f"{new!r} is not a file name or full path")
            elif not rows:
                problems.append(f"no media row uses {old}")
            elif windows_file_modified(old) is None:
                problems.append(f"file not found: {old}")
            elif windows_file_modified(f"{new_folder}\\{new_name}") is not None:
                problems.append(f"already exists: {new_folder}\\{new_name}")
            plans.append((old, folder, name, new_folder, new_name, rows))
    finally:
        conn.close()

    for old, folder, name, new_folder, new_name, rows in plans:
        target = new_name if new_folder == folder else f"{new_folder}\\{new_name}"
        print(f"{old} -> {target} (media {', '.join(f'M{m}' for m in rows) or 'none'})")
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
    done = []
    try:
        for old, folder, name, new_folder, new_name, rows in plans:
            for mid in rows:
                if new_folder == folder:  # each row keeps its own spelling of the folder
                    cur = conn.execute("UPDATE MultimediaTable SET MediaFile = ?, UTCModDate = ? WHERE MediaID = ?",
                                       (new_name, stamp, mid))
                else:
                    cur = conn.execute("UPDATE MultimediaTable SET MediaPath = ?, MediaFile = ?, UTCModDate = ?"
                                       " WHERE MediaID = ?", (new_folder, new_name, stamp, mid))
                if cur.rowcount != 1:
                    raise RuntimeError(f"media M{mid} not updated")
            if new_folder == folder:
                rename_windows_file(old, new_name)
            else:
                move_windows_file(old, f"{new_folder}\\{new_name}")
            done.append((old, folder, name, new_folder, new_name))
        conn.commit()
    except Exception:
        conn.rollback()
        for old, folder, name, new_folder, new_name in reversed(done):
            if new_folder == folder:
                rename_windows_file(f"{folder}\\{new_name}", name)
            else:
                move_windows_file(f"{new_folder}\\{new_name}", old)
        raise
    finally:
        conn.close()
    print(f"Applied: {len(plans)} files and {sum(len(p[5]) for p in plans)} media rows renamed."
          " Run RootsMagic's rebuild indexes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
