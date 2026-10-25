"""Link one citation to one event (fact), with a quality rating.

For a citation linked to more than one person (e.g. a marriage record cited on both
partners' facts), where link_citations_to_fact.py cannot choose the person. The new
link copies RootsMagic's own rows: OwnerType 2 (event), IsPrivate 0, Flags 0.

Refused: the citation or event does not exist, or the event already has the citation.

Dry run by default: prints the link. --apply writes it in one transaction. RootsMagic
must be closed, and the file must be a working copy.

Usage: python link_citation.py PATH_TO_RMTREE --citation ID --event ID --quality XYZ [--apply]
"""

import argparse
import re
import sys

from rmutils import connect_readonly, connect_readwrite, db_path_arg, utc_mod_date

OWNER_EVENT = 2


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="link_citation.py PATH_TO_RMTREE")
    parser.add_argument("--citation", type=int, required=True)
    parser.add_argument("--event", type=int, required=True)
    parser.add_argument("--quality", required=True, help="three characters, e.g. SIX")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(sys.argv[2:])
    if not re.fullmatch(r"[PS~][DIN~][OX~]", args.quality):
        print(f"Quality {args.quality!r} is not three characters P/S/~, D/I/N/~, O/X/~")
        return 1

    conn = connect_readonly(path)
    try:
        citation = conn.execute("SELECT 1 FROM CitationTable WHERE CitationID = ?", (args.citation,)).fetchone()
        event = conn.execute("SELECT EventType, OwnerType, OwnerID, Date FROM EventTable WHERE EventID = ?",
                             (args.event,)).fetchone()
        linked = conn.execute("SELECT 1 FROM CitationLinkTable WHERE CitationID = ? AND OwnerType = ?"
                              " AND OwnerID = ?", (args.citation, OWNER_EVENT, args.event)).fetchone()
    finally:
        conn.close()
    problems = []
    if not citation:
        problems.append(f"C{args.citation} not found")
    if not event:
        problems.append(f"E{args.event} not found")
    if linked:
        problems.append(f"E{args.event} already has C{args.citation}")
    if problems:
        print("Not changed: " + "; ".join(problems))
        return 1

    fact, owner_type, owner, date = event
    print(f"Link C{args.citation} -> E{args.event} (fact {fact}, owner type {owner_type} ID {owner}, {date})"
          f" {args.quality}")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0
    conn = connect_readwrite(path)
    try:
        conn.execute("INSERT INTO CitationLinkTable (CitationID, OwnerType, OwnerID, Quality, IsPrivate, Flags,"
                     " UTCModDate) VALUES (?, ?, ?, ?, 0, 0, ?)",
                     (args.citation, OWNER_EVENT, args.event, args.quality, utc_mod_date()))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print("Applied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
