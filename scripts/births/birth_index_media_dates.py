"""Make birth index scan dates the plain registration quarter.

For every media item attached to citations of the given sources (default 583
and 590), the registration quarter comes from the citation's Citing field
("Births registered in January, February, and March 1886"). The scan's date
becomes that quarter as a plain range, "D-+18860100..+18860300..", with
SortDate from rmutils.sort_date.
  Changed: dates over the same quarter in another style ("about", "between").
  Listed, not changed: dates over a different quarter or in another form
  (unless named with --include), and scans whose citations give different
  quarters.
  Left alone: blank dates.

Dry run by default: writes the proposed changes to
tmp/output/birth_register/<timestamp>_birth_index_media_dates.txt and changes nothing.
--apply writes them in one transaction. RootsMagic must be closed, and the
file must be a working copy.

Usage: python birth_index_media_dates.py PATH_TO_RMTREE [--source ID ...]
           [--include MEDIA_ID ...] [--apply]
"""

import argparse
import re
import sys
from collections import defaultdict

from rmutils import (
    connect_readonly,
    connect_readwrite,
    db_path_arg,
    output_file,
    read_fields,
    sort_date,
    utc_mod_date,
)

OWNER_CITATION = 4
NO_DATE = "."
CITING = re.compile(r"Births registered in (?P<first>\w+), .* (?P<year>\d{4})$")
FIRST_MONTH = {"January": 1, "April": 4, "July": 7, "October": 10}


def quarter_range(year: int, first: int) -> str:
    return f"D-+{year}{first:02}00..+{year}{first + 2:02}00.."


def same_quarter(date: str, target: str) -> bool:
    """date covers the same months as target, whatever its range style or "about"."""
    return (
        len(date) >= 24 and date[:2] in ("D-", "DR") and date[13] == "+"
        and date[3:11] == target[3:11] and date[14:22] == target[14:22]
    )


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="birth_index_media_dates.py PATH_TO_RMTREE")
    parser.add_argument("--source", type=int, nargs="+", default=[583, 590])
    parser.add_argument("--include", type=int, nargs="*", default=[],
                        help="media IDs to set to the citation's quarter even if their date differs")
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])

    marks = ",".join("?" * len(args.source))
    conn = connect_readonly(path)
    try:
        rows = conn.execute(
            f"""SELECT m.MediaID, m.MediaFile, m.Date, c.Fields
                FROM MultimediaTable m
                JOIN MediaLinkTable ml ON ml.MediaID = m.MediaID AND ml.OwnerType = ?
                JOIN CitationTable c ON c.CitationID = ml.OwnerID
                WHERE c.SourceID IN ({marks}) ORDER BY m.MediaID""",
            (OWNER_CITATION, *args.source),
        ).fetchall()
    finally:
        conn.close()

    media, targets = {}, defaultdict(set)
    for mid, file, date, blob in rows:
        media[mid] = (file, date or NO_DATE)
        match = CITING.search(read_fields(blob).get("Citing", ""))
        if match and match.group("first") in FIRST_MONTH:
            targets[mid].add(quarter_range(int(match.group("year")), FIRST_MONTH[match.group("first")]))

    changes, listed, unchanged, blank = [], [], 0, 0
    for mid, (file, date) in media.items():
        if date == NO_DATE:
            blank += 1
        elif len(targets[mid]) != 1:
            listed.append((mid, file, date, "citations give no single registration quarter"))
        else:
            target = next(iter(targets[mid]))
            if date == target:
                unchanged += 1
            elif same_quarter(date, target) or mid in args.include:
                changes.append((mid, file, date, target, sort_date(target)))
            else:
                listed.append((mid, file, date, f"differs from the citation's quarter {target}"))

    with output_file("birth_index_media_dates", "birth_register"):
        print(f"Scans: {len(media)}; change {len(changes)}; already plain {unchanged};"
              f" blank {blank}; listed {len(listed)}")
        if listed:
            print("\n== Listed, not changed")
            for mid, file, date, why in listed:
                print(f"   M{mid} {file} {date}: {why}")
        print("\n== Proposed changes")
        for mid, file, date, target, sort in changes:
            print(f"   M{mid} {file}: {date} -> {target} (SortDate {sort})")
    print(f"{len(changes)} scan dates to change; {len(listed)} listed")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    try:
        for mid, _, date, target, sort in changes:
            cur = conn.execute(
                "UPDATE MultimediaTable SET Date = ?, SortDate = ?, UTCModDate = ?"
                " WHERE MediaID = ? AND Date = ?",
                (target, sort, stamp, mid, date),
            )
            if cur.rowcount != 1:
                raise RuntimeError(f"media M{mid} not updated")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"Applied: {len(changes)} scan dates changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
