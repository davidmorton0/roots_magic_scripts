"""List the scan files in a Records folder with their last-modified dates (read-only).

FOLDER is a full Windows path, or a path under scan_root (config), e.g.
"Marriage - Church\\Britain". Files in subfolders named in skip_subfolders (config) or
named "Unsorted" are left out (G19). The last-modified date is the one used as a
citation's access date (G16). With --tree, each file also shows the media rows that use
it, or "not in the tree".

Usage: python list_scans.py FOLDER [--tree PATH_TO_RMTREE] [--config FILE]
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path, PureWindowsPath

from rmutils import access_date_text, connect_readonly, list_windows_files_with_dates, load_config

ALWAYS_SKIPPED = {"unsorted"}


def main() -> int:
    parser = argparse.ArgumentParser(prog="list_scans.py", description=__doc__.splitlines()[0])
    parser.add_argument("folder")
    parser.add_argument("--tree", type=Path)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args(sys.argv[1:])
    config = load_config(args.config)
    folder = args.folder if ":" in args.folder or args.folder.startswith("\\\\") else \
        f"{config['scan_root'].rstrip(chr(92))}\\{args.folder.strip(chr(92))}"
    skipped = {s.lower() for s in config.get("skip_subfolders", [])} | ALWAYS_SKIPPED

    files = {}
    for path, modified in list_windows_files_with_dates(folder):
        relative = PureWindowsPath(path[len(folder):].lstrip("\\"))
        if not any(part.lower() in skipped for part in relative.parts[:-1]):
            files[path] = (str(relative), modified)

    used = defaultdict(list)
    if args.tree:
        conn = connect_readonly(args.tree)
        try:
            for mid, media_path, media_file in conn.execute("SELECT MediaID, MediaPath, MediaFile FROM MultimediaTable"):
                used[f"{(media_path or '').rstrip(chr(92))}\\{media_file or ''}".lower()].append(mid)
        finally:
            conn.close()

    print(folder)
    for path, (relative, modified) in sorted(files.items(), key=lambda item: item[1][0].lower()):
        line = f"   {relative}  {access_date_text(modified)}"
        if args.tree:
            mids = used.get(path.lower())
            line += "  " + (", ".join(f"M{m}" for m in mids) if mids else "not in the tree")
        print(line)
    print(f"{len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
