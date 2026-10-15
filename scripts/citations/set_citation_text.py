"""Set the transcription (ActualText) of citations that have none.

Refuses to overwrite a citation that already has a transcription.

Dry run by default: prints the new text. --apply writes it in one transaction.
RootsMagic must be closed, and the file must be a working copy.

Usage: python set_citation_text.py PATH_TO_RMTREE --text CITATION_ID TEXT
           [--text CITATION_ID TEXT ...] [--apply]
"""

import argparse
import sys

from rmutils import connect_readonly, connect_readwrite, db_path_arg, utc_mod_date


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="set_citation_text.py PATH_TO_RMTREE")
    parser.add_argument("--text", nargs=2, action="append", required=True,
                        metavar=("CITATION_ID", "TEXT"))
    parser.add_argument("--apply", action="store_true", help="write the transcriptions")
    args = parser.parse_args(sys.argv[2:])
    texts = {int(cid): text for cid, text in args.text}

    conn = connect_readonly(path)
    try:
        marks = ",".join("?" * len(texts))
        current = dict(conn.execute(
            f"SELECT CitationID, ActualText FROM CitationTable WHERE CitationID IN ({marks})", list(texts)
        ))
    finally:
        conn.close()
    missing = sorted(set(texts) - set(current))
    filled = sorted(cid for cid in current if (current[cid] or "").strip())
    if missing:
        print(f"Citations not found: {missing}")
        return 1
    if filled:
        print(f"Citations already have a transcription: {filled}")
        return 1

    for cid, text in texts.items():
        print(f"C{cid}:")
        for line in text.splitlines():
            print(f"   {line}")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    try:
        for cid, text in texts.items():
            conn.execute("UPDATE CitationTable SET ActualText = ?, UTCModDate = ? WHERE CitationID = ?",
                         (text, stamp, cid))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"Applied: {len(texts)} transcriptions set.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
