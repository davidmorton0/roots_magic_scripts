"""Fill the media details of death index scans in one pass.

For every media item attached to a citation of a death index source (default
589, FreeBMD; already on template 6, see freebmd_deaths.py), set:
  Caption      "Surname, Given – death index – YYYY Qn" with the name as
               printed in the index (user's choice, 2026-10-16), so a married
               woman sorts under the name the image shows; from 1984, when
               the index is yearly, "– YYYY Mon" (month of registration)
  RefNumber    the GRO reference: "YYYY Qn District Volume Page"
               (from 1984: "YYYY Mon District Volume Page")
  Description  the index entry, then where the image came from
  Date         the registration quarter as a range ("D-+YYYYMM00..+YYYYMM00..";
               from 1984 the month, "D.+YYYYMM00..+00000000.."), with the
               SortDate RootsMagic already uses for that exact date string
               elsewhere in the tree, else rmutils.sort_date
Values come from the citation fields (SpecificItem and Citing). Ancestry's
entries from 1993 give register, district and subdistrict and entry instead of
volume and page; RefNumber then ends "Register DistrictSubdistrict Entry".

A field that already has a value is not overwritten; such media are listed.
Media whose citations point at different entries are skipped and listed;
with --split, the first citation keeps the media row and each other citation
gets its own copy of the row (same file, thumbnail and type), with its media
link moved to the copy, so each entry has its own details (user's choice,
2026-10-16).

Dry run by default: writes the proposed changes to
tmp/output/death_register/<timestamp>_death_index_media.txt and changes nothing.
--apply writes them in one transaction. RootsMagic must be closed, and the
file must be a working copy.

Usage: python death_index_media.py PATH_TO_RMTREE [--source ID] [--origin TEXT] [--split]
           [--apply]
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
    read_fields,
    sort_date,
    utc_mod_date,
)

DEFAULT_SOURCE = 589
OWNER_CITATION = 4
NO_DATE = "."
IMAGE_ORIGIN = "Image of the General Register Office printed death index page, from FreeBMD."
DATE_TABLES = ("EventTable", "MultimediaTable")
MONTHS = ("January February March April May June July August September"
          " October November December").split()

ENTRY = re.compile(
    r"^entry for (?P<name>.+?), (?:age \d+, |born [^,]+, )?(?P<district>[^,]+?)"
    r"(?:, registered (?P<month>\w+) (?P<year>\d{4}))?, "
    r"(?:vol\. (?P<volume>\S+), p\. (?P<page>[^,;]+)"
    r"|register (?P<register>[^,]+), district and subdistrict (?P<dsd>[^,]+), entry (?P<entry>[^,;]+))"
    r"(?P<rest>;.*)?$"
)
QUARTERLY = re.compile(r"Deaths registered in (?P<first>\w+), .* (?P<year>\d{4})$")
QUARTER = {"January": 1, "April": 2, "July": 3, "October": 4}


@dataclass
class Entry:
    surname: str
    given: str
    text: str
    when: str  # "YYYY Qn" or "YYYY Mon"
    date: str
    district: str
    volume: str
    page: str


@dataclass
class Plan:
    media_id: int
    file: str
    current: dict[str, object]
    new: dict[str, object] = field(default_factory=dict)
    kept: list[str] = field(default_factory=list)
    problem: str = ""
    copy_link: int = 0  # with --split: media link to move to a new copy of the row
    citation_id: int = 0


def index_name(text: str) -> tuple[str, str] | None:
    """(surname, given) from the first entry line of a FreeBMD-layout transcription."""
    lines = [line for line in (text or "").replace("\r", "").split("\n") if line.strip()]
    if len(lines) < 2:
        return None
    cols = lines[1].split("\t")
    if len(cols) < 2:
        return None

    def tidy(part: str) -> str:
        part = " ".join(part.split())
        return part.title() if part.isupper() else part

    return tidy(cols[0]), tidy(cols[1])


def parse_entry(cid: int, fields: dict[str, str], text: str) -> Entry | str:
    item = fields.get("SpecificItem", "")
    citing = fields.get("Citing", "")
    entry = ENTRY.match(item)
    name = index_name(text)
    if not entry or not name:
        return f"C{cid}: citation fields or transcription not in the expected form"
    quarterly = QUARTERLY.search(citing)
    if quarterly and quarterly.group("first") in QUARTER:
        year, quarter = quarterly.group("year"), QUARTER[quarterly.group("first")]
        first = quarter * 3 - 2
        when = f"{year} Q{quarter}"
        date = f"D-+{year}{first:02}00..+{year}{first + 2:02}00.."
        heading = quarterly.group(0)
    elif entry.group("month") in MONTHS:  # yearly index, or Ancestry's Citing
        month = MONTHS.index(entry.group("month")) + 1
        when = f"{entry.group('year')} {entry.group('month')[:3]}"
        date = f"D.+{entry.group('year')}{month:02}00..+00000000.."
        heading = f"Deaths registered in {entry.group('year')}"
    else:
        return f"C{cid}: Citing not in the expected form"
    if entry.group("volume"):
        volume, page = entry.group("volume"), entry.group("page").strip()
    else:  # Ancestry, 1993 on: register, district and subdistrict, entry
        volume = f"{entry.group('register')} {entry.group('dsd')}"
        page = entry.group("entry").strip()
    return Entry(
        name[0], name[1], f"{heading}: {item.removeprefix('entry for ')}", when, date,
        entry.group("district"), volume, page,
    )


def plan_media(media_id, file, current, entries: list[Entry | str], known: dict[str, int],
               origin: str = IMAGE_ORIGIN) -> Plan:
    plan = Plan(media_id, file, current)
    problems = [e for e in entries if isinstance(e, str)]
    if problems:
        plan.problem = "; ".join(problems)
        return plan
    if len({(e.when, e.district, e.volume, e.page) for e in entries}) > 1:
        plan.problem = "attached to citations for different entries"
        return plan
    e = entries[0]
    wanted = {
        "Caption": f"{e.surname}, {e.given} – death index – {e.when}",
        "RefNumber": f"{e.when} {e.district} {e.volume} {e.page}",
        "Description": f"{e.text}. {origin}",
        "Date": e.date,
    }
    for name in ("Caption", "RefNumber", "Description", "Date"):
        if current[name] in (None, "", NO_DATE):
            plan.new[name] = wanted[name]
        elif current[name] != wanted[name]:
            plan.kept.append(f"{name} already '{current[name]}'")
    if "Date" in plan.new:
        plan.new["SortDate"] = known.get(e.date, sort_date(e.date))
    return plan


def known_sort_dates(conn: sqlite3.Connection) -> dict[str, int]:
    known = {}
    for table in DATE_TABLES:
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if {"Date", "SortDate"} <= columns:
            for date, sort in conn.execute(f"SELECT Date, SortDate FROM {table} WHERE Date LIKE 'D%'"):
                known.setdefault(date, sort)
    return known


def build_plans(conn: sqlite3.Connection, source_id: int, origin: str = IMAGE_ORIGIN,
                split: bool = False) -> list[Plan]:
    known = known_sort_dates(conn)
    rows = conn.execute(
        """SELECT m.MediaID, m.MediaPath, m.MediaFile, m.Caption, m.RefNumber, m.Description,
                  m.Date, m.SortDate, c.CitationID, c.Fields, c.ActualText, ml.LinkID
           FROM MultimediaTable m
           JOIN MediaLinkTable ml ON ml.MediaID = m.MediaID AND ml.OwnerType = ?
           JOIN CitationTable c ON c.CitationID = ml.OwnerID AND c.SourceID = ?
           ORDER BY m.MediaID, c.CitationID""",
        (OWNER_CITATION, source_id),
    ).fetchall()
    media, entries, links = {}, defaultdict(list), defaultdict(list)
    for mid, path, file, caption, ref, descr, date, sort, cid, blob, text, link in rows:
        media[mid] = (
            f"{(path or '').rstrip(chr(92))}\\{file or ''}",
            {"Caption": caption, "RefNumber": ref, "Description": descr, "Date": date, "SortDate": sort},
        )
        entries[mid].append(parse_entry(cid, read_fields(blob), text or ""))
        links[mid].append((link, cid))
    plans = []
    for mid in media:
        plan = plan_media(mid, *media[mid], entries[mid], known, origin)
        if not (split and plan.problem == "attached to citations for different entries"):
            plans.append(plan)
            continue
        empty = {"Caption": "", "RefNumber": "", "Description": "", "Date": NO_DATE, "SortDate": 0}
        for i, (entry, (link, cid)) in enumerate(zip(entries[mid], links[mid])):
            part = plan_media(mid, media[mid][0], media[mid][1] if i == 0 else empty, [entry], known, origin)
            part.citation_id = cid
            if i:
                part.copy_link = link
            plans.append(part)
    return plans


def write_report(plans: list[Plan]) -> None:
    problems = [p for p in plans if p.problem]
    kept = [p for p in plans if p.kept and not p.problem]
    changing = [p for p in plans if p.new and not p.problem]
    print(f"Media: {len(plans)}; to update {len(changing)}; skipped {len(problems)};"
          f" with existing values kept {len(kept)}")
    if problems:
        print("\n== Skipped")
        for p in problems:
            print(f"   M{p.media_id} {p.file}: {p.problem}")
    if kept:
        print("\n== Existing values kept (not overwritten)")
        for p in kept:
            print(f"   M{p.media_id} {p.file}: {'; '.join(p.kept)}")
    print("\n== Proposed media changes")
    for p in changing:
        if p.copy_link:
            print(f"\nNew copy of M{p.media_id} {p.file} for C{p.citation_id}"
                  f" (media link {p.copy_link} moves to it)")
        else:
            print(f"\nM{p.media_id} {p.file}" + (f" (C{p.citation_id})" if p.citation_id else ""))
        for name, value in p.new.items():
            print(f"   {name + ':':<13}{value}")


def apply(path, plans: list[Plan]) -> int:
    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    count = 0
    try:
        for p in plans:
            if p.problem or not p.new:
                continue
            if p.copy_link:
                cur = conn.execute(
                    """INSERT INTO MultimediaTable (MediaType, MediaPath, MediaFile, URL, Thumbnail,
                           Caption, RefNumber, Date, SortDate, Description, UTCModDate)
                       SELECT MediaType, MediaPath, MediaFile, URL, Thumbnail,
                           '', '', '.', 0, '', ? FROM MultimediaTable WHERE MediaID = ?""",
                    (stamp, p.media_id),
                )
                new_id = cur.lastrowid
                cur = conn.execute(
                    "UPDATE MediaLinkTable SET MediaID = ?, UTCModDate = ? WHERE LinkID = ? AND MediaID = ?",
                    (new_id, stamp, p.copy_link, p.media_id),
                )
                if cur.rowcount != 1:
                    raise RuntimeError(f"media link {p.copy_link} not moved")
                p.media_id = new_id
            columns = ", ".join(f"{name} = ?" for name in p.new)
            cur = conn.execute(
                f"UPDATE MultimediaTable SET {columns}, UTCModDate = ? WHERE MediaID = ?",
                (*p.new.values(), stamp, p.media_id),
            )
            if cur.rowcount != 1:
                raise RuntimeError(f"media M{p.media_id} not updated")
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
    parser = argparse.ArgumentParser(prog="death_index_media.py PATH_TO_RMTREE")
    parser.add_argument("--source", type=int, default=DEFAULT_SOURCE)
    parser.add_argument("--origin", default=IMAGE_ORIGIN,
                        help="image-origin sentence for the description (default: from FreeBMD)")
    parser.add_argument("--split", action="store_true",
                        help="give each entry on a shared scan its own copy of the media row")
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])

    conn = connect_readonly(path)
    try:
        plans = build_plans(conn, args.source, args.origin, args.split)
    finally:
        conn.close()

    changing = sum(1 for p in plans if p.new and not p.problem)
    skipped = sum(1 for p in plans if p.problem)
    with output_file("death_index_media", "death_register"):
        write_report(plans)
    print(f"{len(plans)} media; {changing} to update; {skipped} skipped")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0
    print(f"Applied: {apply(path, plans)} media updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
