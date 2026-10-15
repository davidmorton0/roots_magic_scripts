"""Set the quality of citation links that are still unassessed.

CitationLinkTable.Quality holds three characters, as RootsMagic 12 wrote them
when set by hand (2026-10-15):
  1 information  P primary, S secondary, ~ not set
  2 evidence     D direct, I indirect, N negative, ~ not set
  3 source       O original (not seen yet), X derivative, ~ not set
"PIX" = primary information, indirect evidence, derivative source.

For every link of the given sources' citations whose quality is "~~~", set
--quality. Links with any other value are left alone and counted.

Dry run by default: prints what would change. --apply writes it in one
transaction. RootsMagic must be closed, and the file must be a working copy.

Usage: python set_citation_quality.py PATH_TO_RMTREE --source ID [ID ...] --quality XYZ [--apply]
"""

import argparse
import re
import sys
from collections import Counter

from rmutils import connect_readonly, connect_readwrite, db_path_arg, utc_mod_date

UNSET = "~~~"
QUALITY = re.compile(r"^[PS~][DIN~][OX~]$")


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="set_citation_quality.py PATH_TO_RMTREE")
    parser.add_argument("--source", type=int, nargs="+", required=True)
    parser.add_argument("--quality", required=True, help='three characters, e.g. "PIX"')
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])
    if not QUALITY.match(args.quality):
        print(f"Quality '{args.quality}' is not information (P/S/~), evidence (D/I/N/~), source (O/X/~)")
        return 1

    marks = ",".join("?" * len(args.source))
    conn = connect_readonly(path)
    try:
        links = conn.execute(
            f"""SELECT cl.LinkID, cl.Quality FROM CitationLinkTable cl
                JOIN CitationTable c USING (CitationID) WHERE c.SourceID IN ({marks})
                ORDER BY cl.LinkID""",
            args.source,
        ).fetchall()
    finally:
        conn.close()

    to_set = [link_id for link_id, quality in links if (quality or UNSET) == UNSET]
    kept = Counter(quality for _, quality in links if (quality or UNSET) != UNSET)
    print(f"Citation links: {len(links)}; set to '{args.quality}': {len(to_set)};"
          f" already assessed, kept: {sum(kept.values())} {dict(kept)}")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    try:
        for link_id in to_set:
            conn.execute(
                "UPDATE CitationLinkTable SET Quality = ?, UTCModDate = ? WHERE LinkID = ? AND Quality = ?",
                (args.quality, stamp, link_id, UNSET),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"Applied: {len(to_set)} citation links set.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
