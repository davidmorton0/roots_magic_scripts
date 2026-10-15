"""Move citations from birth register events to the person's Birth event.

For every citation linked to a birth register event (default fact type 1024,
"Birth Register - UK"; --register-fact 1025 for "Birth Register Ireland"),
whatever its source, point the link at the same person's Birth event (fact
type 1) instead. The link row is updated in place,
so its quality, sort order and other settings are kept. The register events
are not changed or deleted; they are left without that citation.

Not moved (listed instead): the person has no Birth event, or more than one
primary Birth event; the Birth event already has the citation.
Moved but flagged: the Birth date does not fit the registration quarter
(after the quarter ends, or more than a year before it starts). Only the year
and month of the first date in RootsMagic's date code are read.

Dry run by default: writes the proposed changes to
tmp/output/birth_register/<timestamp>_move_citations_to_birth.txt and changes nothing.
--apply writes them in one transaction. RootsMagic must be closed, and the
file must be a working copy.

Usage: python move_citations_to_birth.py PATH_TO_RMTREE [--register-fact ID] [--apply]
"""

import argparse
import re
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass, field

from rmutils import (
    connect_readonly,
    connect_readwrite,
    db_path_arg,
    output_file,
    person_names,
    read_fields,
    utc_mod_date,
)

OWNER_PERSON, OWNER_EVENT = 0, 2
FACT_BIRTH, FACT_BIRTH_REGISTER = 1, 1024
CITING = re.compile(r"Births registered in (?P<first>\w+), .* (?P<year>\d{4})$")
QUARTER_START = {"January": 1, "April": 4, "July": 7, "October": 10}


@dataclass
class Move:
    link_id: int
    citation_id: int
    person: int
    from_event: int
    to_event: int = 0
    issues: list[str] = field(default_factory=list)
    problem: str = ""


def year_month(date: str | None) -> tuple[int, int] | None:
    """(year, month) of the first date in a RootsMagic date code, or None."""
    if date and len(date) >= 9 and date[0] == "D" and date[2] in "+-" and date[3:9].isdigit():
        year, month = int(date[3:7]), int(date[7:9])
        if year:
            return year, month
    return None


def fits_quarter(birth: tuple[int, int], citing: str) -> str:
    """'' if a birth (year, month) fits the registration quarter in Citing, else why not."""
    match = CITING.search(citing)
    if not match or match.group("first") not in QUARTER_START:
        return ""
    start = int(match.group("year")) * 12 + QUARTER_START[match.group("first")] - 1
    born = birth[0] * 12 + birth[1] - 1 if birth[1] else birth[0] * 12
    if born > start + 2:
        return "Birth date is after the registration quarter"
    if born < start - 12:
        return "Birth date is more than a year before the registration quarter"
    return ""


def build_moves(conn: sqlite3.Connection, register_fact: int = FACT_BIRTH_REGISTER) -> list[Move]:
    births = defaultdict(list)
    for eid, owner, primary, date in conn.execute(
        "SELECT EventID, OwnerID, IsPrimary, Date FROM EventTable"
        " WHERE OwnerType = ? AND EventType = ?",
        (OWNER_PERSON, FACT_BIRTH),
    ):
        births[owner].append((eid, primary, date))
    existing = {
        (cid, oid)
        for cid, oid in conn.execute(
            "SELECT CitationID, OwnerID FROM CitationLinkTable WHERE OwnerType = ?",
            (OWNER_EVENT,),
        )
    }
    rows = conn.execute(
        """SELECT cl.LinkID, cl.CitationID, e.EventID, e.OwnerID, c.Fields
           FROM CitationLinkTable cl
           JOIN CitationTable c USING (CitationID)
           JOIN EventTable e ON e.EventID = cl.OwnerID
           WHERE cl.OwnerType = ? AND e.EventType = ? AND e.OwnerType = ?
           ORDER BY cl.CitationID""",
        (OWNER_EVENT, register_fact, OWNER_PERSON),
    ).fetchall()

    moves = []
    for link_id, cid, from_event, person, blob in rows:
        move = Move(link_id, cid, person, from_event)
        candidates = births.get(person, [])
        primary = [b for b in candidates if b[1]]
        chosen = primary if primary else candidates
        if not candidates:
            move.problem = "person has no Birth event"
        elif len(chosen) > 1:
            move.problem = f"person has {len(chosen)} {'primary ' if primary else ''}Birth events"
        else:
            move.to_event, _, date = chosen[0]
            if (cid, move.to_event) in existing:
                move.problem = f"Birth event E{move.to_event} already has this citation"
            else:
                birth = year_month(date)
                why = fits_quarter(birth, read_fields(blob).get("Citing", "")) if birth else ""
                if why:
                    move.issues.append(why)
        moves.append(move)
    return moves


def write_report(moves: list[Move], names: dict[int, str], dates: dict[int, str]) -> None:
    problems = [m for m in moves if m.problem]
    flagged = [m for m in moves if m.issues and not m.problem]
    print(f"Citation links: {len(moves)}; move {len(moves) - len(problems)};"
          f" not moved {len(problems)}; flagged {len(flagged)}")
    if problems:
        print("\n== Not moved")
        for m in problems:
            print(f"   C{m.citation_id} {names.get(m.person, '?')} [P{m.person}]: {m.problem}")
    if flagged:
        print("\n== Moved but please check")
        for m in flagged:
            for issue in m.issues:
                print(f"   C{m.citation_id} {names.get(m.person, '?')} [P{m.person}]: {issue}"
                      f" (Birth {dates.get(m.to_event)}, register {dates.get(m.from_event)})")
    print("\n== Proposed moves")
    for m in moves:
        if not m.problem:
            print(f"   C{m.citation_id} {names.get(m.person, '?')} [P{m.person}]:"
                  f" E{m.from_event} {dates.get(m.from_event)} -> E{m.to_event} {dates.get(m.to_event)}")


def apply(path, moves: list[Move]) -> int:
    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    count = 0
    try:
        for m in moves:
            if m.problem:
                continue
            cur = conn.execute(
                "UPDATE CitationLinkTable SET OwnerID = ?, UTCModDate = ?"
                " WHERE LinkID = ? AND OwnerType = ? AND OwnerID = ?",
                (m.to_event, stamp, m.link_id, OWNER_EVENT, m.from_event),
            )
            if cur.rowcount != 1:
                raise RuntimeError(f"citation link {m.link_id} not updated")
            count += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return count


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="move_citations_to_birth.py PATH_TO_RMTREE")
    parser.add_argument("--register-fact", type=int, default=FACT_BIRTH_REGISTER,
                        help="fact type of the register events (default 1024, Birth Register - UK)")
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])

    conn = connect_readonly(path)
    try:
        moves = build_moves(conn, args.register_fact)
        names = person_names(conn)
        dates = dict(conn.execute("SELECT EventID, Date FROM EventTable"))
    finally:
        conn.close()

    problems = sum(1 for m in moves if m.problem)
    with output_file("move_citations_to_birth", "birth_register"):
        write_report(moves, names, dates)
    print(f"{len(moves)} citation links; {len(moves) - problems} to move; {problems} not moved")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0
    print(f"Applied: {apply(path, moves)} citation links moved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
