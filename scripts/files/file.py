"""File operations on the Windows drive (no database). WSL cannot see H:, so each runs through
PowerShell (rmutils).

  list    FOLDER [--skip]              Files under the folder with their last-modified dates (read-only).
  info    PATH                         Whether the file exists, its last-modified date and SHA-256 hash
                                       (read-only).
  rename  PATH NEW_NAME                Rename the file in its folder.
  move    PATH NEW_PATH                Move the file to a full new path (folder created if missing).
  copy    PATH NEW_PATH [--overwrite]  Copy the file, then compare the two hashes.

A path is a full Windows path (H:\\..., or \\\\server\\...), or a path under scan_root (config), e.g.
"Marriage - Church\\Britain". --skip leaves out files in subfolders named in skip_subfolders (config)
or named "Unsorted", as list_scans.py does. The last-modified date is the one used as a citation's
access date (G16).

Media rows that use a file are not changed here: use records/media.py (get --path, edit --path).

Refused when the file does not exist, NEW_NAME is not a plain file name, or the target exists (copy:
unless --overwrite). rename, move and copy are dry runs by default: they print what would change.
--apply does it.

Usage: python file.py [--config FILE] list|info|rename|move|copy ... [--apply]
"""

import argparse
import sys
from pathlib import Path, PureWindowsPath

from rmutils import (
    access_date_text,
    copy_windows_file,
    list_windows_files_with_dates,
    load_config,
    move_windows_file,
    rename_windows_file,
    stop_unless_applying,
    windows_file_hash,
    windows_file_modified,
)

ALWAYS_SKIPPED = {"unsorted"}


def full_path(text: str, config: dict) -> str:
    """A full Windows path as given, or the path under scan_root."""
    if ":" in text or text.startswith("\\\\"):
        return text.rstrip("\\")
    return f"{config['scan_root'].rstrip(chr(92))}\\{text.strip(chr(92))}"


def list_files(args, config: dict) -> int:
    folder = full_path(args.folder, config)
    skipped = {s.lower() for s in config.get("skip_subfolders", [])} | ALWAYS_SKIPPED if args.skip else set()
    files = []
    for path, modified in list_windows_files_with_dates(folder):
        relative = PureWindowsPath(path[len(folder):].lstrip("\\"))
        if not any(part.lower() in skipped for part in relative.parts[:-1]):
            files.append((str(relative), modified))
    print(folder)
    for relative, modified in sorted(files, key=lambda f: f[0].lower()):
        print(f"   {relative}  {access_date_text(modified)}")
    print(f"{len(files)} files")
    return 0


def info(args, config: dict) -> int:
    path = full_path(args.path, config)
    modified = windows_file_modified(path)
    if modified is None:
        print(f"{path}: not found")
        return 1
    print(path)
    print(f"   modified: {modified.isoformat()} ({access_date_text(modified)})")
    print(f"   SHA-256: {windows_file_hash(path)}")
    return 0


def rename(args, config: dict) -> int:
    path = full_path(args.path, config)
    folder = path.rpartition("\\")[0]
    target = f"{folder}\\{args.new_name}"
    problems = []
    if not args.new_name or any(c in args.new_name for c in "\\/:"):
        problems.append(f"{args.new_name!r} is not a plain file name (use move for another folder)")
    elif windows_file_modified(path) is None:
        problems.append(f"file not found: {path}")
    elif windows_file_modified(target) is not None:
        problems.append(f"already exists: {target}")
    print(f"Rename {path} -> {args.new_name}")
    done = stop_unless_applying(problems, args.apply)
    if done is not None:
        return done
    rename_windows_file(path, args.new_name)
    print("Applied: file renamed.")
    return 0


def move(args, config: dict) -> int:
    path, target = full_path(args.path, config), full_path(args.new_path, config)
    problems = []
    if windows_file_modified(path) is None:
        problems.append(f"file not found: {path}")
    elif windows_file_modified(target) is not None:
        problems.append(f"already exists: {target}")
    print(f"Move {path} -> {target}")
    done = stop_unless_applying(problems, args.apply)
    if done is not None:
        return done
    move_windows_file(path, target)
    print("Applied: file moved.")
    return 0


def copy(args, config: dict) -> int:
    path, target = full_path(args.path, config), full_path(args.new_path, config)
    problems = []
    if windows_file_modified(path) is None:
        problems.append(f"file not found: {path}")
    elif windows_file_modified(target) is not None and not args.overwrite:
        problems.append(f"already exists: {target} (give --overwrite to replace it)")
    print(f"Copy {path} -> {target}")
    done = stop_unless_applying(problems, args.apply)
    if done is not None:
        return done
    copy_windows_file(path, target)
    source_hash, target_hash = windows_file_hash(path), windows_file_hash(target)
    if source_hash != target_hash:
        print(f"Copied, but the hashes differ: {source_hash} / {target_hash}")
        return 1
    print(f"Applied: file copied (SHA-256 {target_hash}).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="file.py", description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, help="settings file (default config.toml)")
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("list")
    p.add_argument("folder")
    p.add_argument("--skip", action="store_true", help="leave out skip_subfolders and Unsorted")
    p.set_defaults(run=list_files)

    p = commands.add_parser("info")
    p.add_argument("path")
    p.set_defaults(run=info)

    p = commands.add_parser("rename")
    p.add_argument("path")
    p.add_argument("new_name")
    p.set_defaults(run=rename)

    for name, run in (("move", move), ("copy", copy)):
        p = commands.add_parser(name)
        p.add_argument("path")
        p.add_argument("new_path")
        p.set_defaults(run=run)
    commands.choices["copy"].add_argument("--overwrite", action="store_true")
    for name in ("rename", "move", "copy"):
        commands.choices[name].add_argument("--apply", action="store_true", help="do it")

    args = parser.parse_args(sys.argv[1:])
    return args.run(args, load_config(args.config))


if __name__ == "__main__":
    sys.exit(main())
