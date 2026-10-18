"""Set a source's text (ActualText): RootsMagic's "Source Text", a description of the source.

Dry run by default: prints the old and new text. --apply writes it in one
transaction. RootsMagic must be closed, and the file must be a working copy.

Usage: python set_source_text.py PATH_TO_RMTREE --text SOURCE_ID TEXT
           [--text SOURCE_ID TEXT ...] [--apply]
"""

import argparse
import sys

from rmutils import connect_readonly, connect_readwrite, db_path_arg, utc_mod_date


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="set_source_text.py PATH_TO_RMTREE")
    parser.add_argument("--text", nargs=2, action="append", required=True,
                        metavar=("SOURCE_ID", "TEXT"))
    parser.add_argument("--apply", action="store_true", help="write the source texts")
    args = parser.parse_args(sys.argv[2:])
    texts = {int(sid): text for sid, text in args.text}

    conn = connect_readonly(path)
    try:
        old = {sid: (name, text) for sid, name, text in conn.execute(
            f"SELECT SourceID, Name, ActualText FROM SourceTable"
            f" WHERE SourceID IN ({','.join('?' * len(texts))})", list(texts))}
    finally:
        conn.close()
    missing = [sid for sid in texts if sid not in old]
    if missing:
        print("Sources not found: " + ", ".join(f"S{sid}" for sid in missing))
        return 1
    for sid, text in texts.items():
        print(f"S{sid} '{old[sid][0]}'\n   {old[sid][1]!r}\n   -> {text!r}")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    try:
        for sid, text in texts.items():
            conn.execute("UPDATE SourceTable SET ActualText = ?, UTCModDate = ? WHERE SourceID = ?",
                         (text, stamp, sid))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"Applied: {len(texts)} source texts set.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
