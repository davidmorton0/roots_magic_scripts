"""Move a new record file from the input folder to its record type's folder, under a new name.

FILE is a file name in input_folder (config). TARGET is the new full Windows path, or a path under
scan_root (config), e.g. "Census\\Britain\\National\\1881\\Images\\SMI-J-NIB-1881.jpg"; the folder
is created if missing. Prints the file's last-modified date (the citation's access date, G16: read
before the move, since Google Drive gives a moved file a new date) and every file in the target
folder with the same base name (the name without extension and without a -R1, -P1, -F1 or -1
suffix), which may be another record of the same name. Refused if FILE does not exist or TARGET
already exists.

The file is not added to the tree here: attach it to its citation with attach_scan.py.

Dry run by default. --apply moves the file.

Usage: python file_input_scan.py FILE TARGET [--apply] [--config FILE]
"""

import argparse
import re
import sys
from pathlib import Path, PureWindowsPath

from rmutils import access_date_text, list_windows_files, load_config, move_windows_file, windows_file_modified

SUFFIX = re.compile(r"-(?:[RPF]\d+|\d)$", re.IGNORECASE)


def base_name(name: str) -> str:
    stem = PureWindowsPath(name).stem
    return SUFFIX.sub("", stem).lower()


def main() -> int:
    parser = argparse.ArgumentParser(prog="file_input_scan.py", description=__doc__.splitlines()[0])
    parser.add_argument("file")
    parser.add_argument("target")
    parser.add_argument("--apply", action="store_true", help="move the file")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    source = str(PureWindowsPath(config["input_folder"]) / args.file)
    target = PureWindowsPath(args.target)
    if not target.drive:
        target = PureWindowsPath(config["scan_root"]) / target
    target_text = str(target)

    modified = windows_file_modified(source)
    if modified is None:
        print(f"Not found: {source}")
        return 1
    print(f"Move {source}\n  -> {target_text}")
    print(f"Last modified (access date, G16): {modified:%Y-%m-%d} ({access_date_text(modified)})")
    if windows_file_modified(target_text) is not None:
        print(f"Refused: {target_text} already exists")
        return 1
    folder = str(target.parent)
    files = list_windows_files(folder) if windows_file_modified(folder) is not None else []
    same = sorted(p for p in files if str(PureWindowsPath(p).parent).lower() == folder.lower()
                  and base_name(p) == base_name(target.name))
    if same:
        print("Same base name in the target folder (check whether they are other records of the same name):")
        for p in same:
            print(f"   {PureWindowsPath(p).name}")
    else:
        print("No file with the same base name in the target folder.")
    if not args.apply:
        print("Dry run: nothing moved.")
        return 0
    move_windows_file(source, target_text)
    print("Moved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
