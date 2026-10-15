"""Set the note (Comments) of one or more citations.

Dry run by default: prints old and new notes. --apply writes them in one
transaction. RootsMagic must be closed, and the file must be a working copy.

Usage: python set_citation_note.py PATH_TO_RMTREE --note CITATION_ID TEXT
           [--note CITATION_ID TEXT ...] [--apply]
"""

import argparse
import sys

from rmutils import connect_readonly, connect_readwrite, db_path_arg, utc_mod_date


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="set_citation_note.py PATH_TO_RMTREE")
    parser.add_argument("--note", nargs=2, action="append", required=True,
                        metavar=("CITATION_ID", "TEXT"))
    parser.add_argument("--apply", action="store_true", help="write the notes")
    args = parser.parse_args(sys.argv[2:])
    notes = {int(cid): text for cid, text in args.note}

    conn = connect_readonly(path)
    try:
        marks = ",".join("?" * len(notes))
        current = dict(conn.execute(
            f"SELECT CitationID, Comments FROM CitationTable WHERE CitationID IN ({marks})", list(notes)
        ))
    finally:
        conn.close()
    missing = sorted(set(notes) - set(current))
    if missing:
        print(f"Citations not found: {missing}")
        return 1

    for cid, text in notes.items():
        print(f"C{cid}: '{current[cid] or ''}' -> '{text}'")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    try:
        for cid, text in notes.items():
            conn.execute("UPDATE CitationTable SET Comments = ?, UTCModDate = ? WHERE CitationID = ?",
                         (text, stamp, cid))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"Applied: {len(notes)} notes set.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
