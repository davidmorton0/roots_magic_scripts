"""Fetch the test tree as the working copy, or push the working copy back over it.

fetch: RootsMagic must be closed. Copies the test tree (config test_tree) over the
working copy (config working_copy), checks both hashes match, and records the hash.

push: RootsMagic must be closed. The test tree's hash must still be the one recorded at
the last fetch or push; if not, RootsMagic saved it since (it saves whenever it is open),
and the push is refused: fetch again, re-run the dry run, apply, then push. Copies the
working copy over the test tree, checks both hashes match, and records the hash.

status: prints both hashes and the recorded one; changes nothing.

The recorded hash is kept in <working copy>.hash beside the working copy.

Usage: python working_copy.py fetch|push|status [--config FILE]
"""

import argparse
import hashlib
import sys
from pathlib import Path

from rmutils import (PROJECT_DIR, copy_windows_file, load_config, rootsmagic_running, windows_file_hash,
                     windows_path)


def file_hash(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser(prog="working_copy.py", description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["fetch", "push", "status"])
    parser.add_argument("--config", type=Path)
    args = parser.parse_args(sys.argv[1:])
    config = load_config(args.config)
    test_tree = config["test_tree"]
    work = PROJECT_DIR / config["working_copy"]
    record = work.with_name(work.name + ".hash")
    recorded = record.read_text().strip() if record.is_file() else None

    if args.action == "status":
        print(f"test tree:    {windows_file_hash(test_tree)}")
        print(f"working copy: {file_hash(work)}")
        print(f"recorded:     {recorded}")
        return 0

    if rootsmagic_running():
        print("RootsMagic is running: close it first. Nothing copied.")
        return 1

    if args.action == "fetch":
        work.parent.mkdir(parents=True, exist_ok=True)
        copy_windows_file(test_tree, windows_path(work))
        source_hash, copy_hash = windows_file_hash(test_tree), file_hash(work)
    else:
        if not work.is_file():
            print(f"No working copy at {work}. Nothing copied.")
            return 1
        current = windows_file_hash(test_tree)
        if current != recorded:
            print(f"The test tree changed since the last fetch or push (now {current}, recorded {recorded}):"
                  " RootsMagic saved it. Fetch again, re-run the dry run and apply, then push. Nothing copied.")
            return 1
        copy_windows_file(windows_path(work), test_tree)
        source_hash, copy_hash = file_hash(work), windows_file_hash(test_tree)

    if source_hash != copy_hash:
        print(f"Hashes differ after the copy: source {source_hash}, copy {copy_hash}. Check the files.")
        return 1
    record.write_text(source_hash + "\n")
    print(f"{args.action}: done, hashes match ({source_hash})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
