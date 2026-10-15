"""Fill the media details of birth index scans in one pass.

For every media item attached to a citation of a birth index source (default
583, FreeBMD; already on template 6), set:
  Caption      "Surname, Given – birth index – YYYY Qn" (person's primary name,
               so the Media page sorts by surname)
  RefNumber    the GRO reference: "YYYY Qn District Volume Page"
  Description  the index entry, then where the image came from
  Date         the registration quarter as a range ("D-+YYYYMM00..+YYYYMM00.."),
               with the SortDate RootsMagic already uses for that exact date
               string elsewhere in the tree, else rmutils.sort_date
Values come from the citation fields (SpecificItem and Citing), not from the
transcription text. A database note at the end of SpecificItem, e.g.
"(England & Wales, Civil Registration Birth Index, 1916-2007)", is kept in the
description.

A field that already has a value is not overwritten; such media are listed.
Media whose citations point at different people or entries are skipped and
listed. Without --origin, the description says the image is from FreeBMD and
citations whose transcription is not in FreeBMD's layout are skipped.

Dry run by default: writes the proposed changes to
tmp/output/birth_register/<timestamp>_birth_index_media.txt and changes nothing.
--apply writes them in one transaction. RootsMagic must be closed, and the
file must be a working copy.

Usage: python birth_index_media.py PATH_TO_RMTREE [--source ID] [--origin TEXT] [--apply]
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

DEFAULT_SOURCE = 583
OWNER_PERSON, OWNER_EVENT, OWNER_CITATION = 0, 2, 4
NO_DATE = "."
NO_SORT_DATE = 9223372036854775807
IMAGE_ORIGIN = "Image of the General Register Office printed birth index page, from FreeBMD."
DATE_TABLES = ("EventTable", "MultimediaTable")

ENTRY = re.compile(
    r"^entry for (?P<name>.+?), (?P<district>.+?), vol\. (?P<volume>\S+), p\. (?P<page>[^,;]+)"
    r"(?:, mother's maiden name (?P<mother>[^;]+))?(?P<rest>;.*)?$"
)
CITING = re.compile(r"Births registered in (?P<first>\w+), .* (?P<year>\d{4})$")
QUARTER = {"January": 1, "April": 2, "July": 3, "October": 4}
FREEBMD_TEXT = re.compile(r"^\s*Births\s+(Mar|Jun|Sep|Dec)\s+\d{4}", re.IGNORECASE)
DATABASE_NOTE = re.compile(r"\s*\([^()]*\)$")  # e.g. " (England & Wales, ... 1916-2007)"


@dataclass
class Entry:
    person: int
    surname: str
    given: str
    text: str
    year: str
    quarter: int
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


def quarter_range(year: str, quarter: int) -> str:
    first = quarter * 3 - 2
    return f"D-+{year}{first:02}00..+{year}{first + 2:02}00.."


def parse_entry(
    cid: int, fields: dict[str, str], transcription: str, person, names,
    check_layout: bool = True,
) -> Entry | str:
    item = fields.get("SpecificItem", "")
    note = DATABASE_NOTE.search(item)
    entry = ENTRY.match(item[: note.start()] if note else item)
    citing = CITING.search(fields.get("Citing", ""))
    if not entry or not citing or citing.group("first") not in QUARTER:
        return f"C{cid}: citation fields not in the expected form"
    if check_layout and transcription and not FREEBMD_TEXT.match(transcription):
        return f"C{cid}: transcription not from FreeBMD, so the image's origin is unknown"
    if person is None:
        return f"C{cid}: not linked to a person's event"
    surname, given = names.get(person, ("", ""))
    return Entry(
        person, surname, given, f"{citing.group(0)}: {item.removeprefix('entry for ')}",
        citing.group("year"), QUARTER[citing.group("first")],
        entry.group("district"), entry.group("volume"), entry.group("page").strip(),
    )


def plan_media(
    media_id, file, current, entries: list[Entry | str], known: dict[str, int],
    origin: str = IMAGE_ORIGIN,
) -> Plan:
    plan = Plan(media_id, file, current)
    problems = [e for e in entries if isinstance(e, str)]
    if problems:
        plan.problem = "; ".join(problems)
        return plan
    keys = {(e.person, e.year, e.quarter, e.district, e.volume, e.page) for e in entries}
    if len(keys) > 1:
        plan.problem = "attached to citations for different people or entries"
        return plan
    e = entries[0]
    date = quarter_range(e.year, e.quarter)
    wanted = {
        "Caption": f"{e.surname}, {e.given} – birth index – {e.year} Q{e.quarter}",
        "RefNumber": f"{e.year} Q{e.quarter} {e.district} {e.volume} {e.page}",
        "Description": f"{e.text}. {origin}",
        "Date": date,
    }
    for name in ("Caption", "RefNumber", "Description", "Date"):
        if current[name] in (None, "", NO_DATE):
            plan.new[name] = wanted[name]
        elif current[name] != wanted[name]:
            plan.kept.append(f"{name} already '{current[name]}'")
    if "Date" in plan.new:
        plan.new["SortDate"] = known.get(date, sort_date(date))
    return plan


def known_sort_dates(conn: sqlite3.Connection) -> dict[str, int]:
    known = {}
    for table in DATE_TABLES:
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if {"Date", "SortDate"} <= columns:
            for date, sort in conn.execute(f"SELECT Date, SortDate FROM {table} WHERE Date LIKE 'D%'"):
                known.setdefault(date, sort)
    return known


def build_plans(conn: sqlite3.Connection, source_id: int, origin: str | None = None) -> list[Plan]:
    """origin: image-origin wording; when given, transcriptions need not be FreeBMD's."""
    names = {
        pid: (surname or "", given or "")
        for pid, surname, given in conn.execute(
            "SELECT OwnerID, Surname, Given FROM NameTable WHERE IsPrimary = 1"
        )
    }
    known = known_sort_dates(conn)
    citation_person = {}
    for cid, otype, oid, e_owner_type, e_owner in conn.execute(
        """SELECT cl.CitationID, cl.OwnerType, cl.OwnerID, e.OwnerType, e.OwnerID
           FROM CitationLinkTable cl JOIN CitationTable c USING (CitationID)
           LEFT JOIN EventTable e ON cl.OwnerType = ? AND e.EventID = cl.OwnerID
           WHERE c.SourceID = ?""",
        (OWNER_EVENT, source_id),
    ):
        if otype == OWNER_PERSON:
            citation_person[cid] = oid
        elif otype == OWNER_EVENT and e_owner_type == OWNER_PERSON:
            citation_person[cid] = e_owner

    rows = conn.execute(
        """SELECT m.MediaID, m.MediaPath, m.MediaFile, m.Caption, m.RefNumber, m.Description,
                  m.Date, m.SortDate, c.CitationID, c.Fields, c.ActualText
           FROM MultimediaTable m
           JOIN MediaLinkTable ml ON ml.MediaID = m.MediaID AND ml.OwnerType = ?
           JOIN CitationTable c ON c.CitationID = ml.OwnerID AND c.SourceID = ?
           ORDER BY m.MediaID, c.CitationID""",
        (OWNER_CITATION, source_id),
    ).fetchall()
    media, entries = {}, defaultdict(list)
    for mid, path, file, caption, ref, descr, date, sort_date, cid, blob, text in rows:
        media[mid] = (
            f"{(path or '').rstrip(chr(92))}\\{file or ''}",
            {"Caption": caption, "RefNumber": ref, "Description": descr,
             "Date": date, "SortDate": sort_date},
        )
        entries[mid].append(
            parse_entry(cid, read_fields(blob), text or "", citation_person.get(cid), names,
                        check_layout=origin is None)
        )
    return [
        plan_media(mid, *media[mid], entries[mid], known, origin or IMAGE_ORIGIN)
        for mid in media
    ]


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
        print(f"\nM{p.media_id} {p.file}")
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
    parser = argparse.ArgumentParser(prog="birth_index_media.py PATH_TO_RMTREE")
    parser.add_argument("--source", type=int, default=DEFAULT_SOURCE)
    parser.add_argument("--origin", help="image-origin sentence for the description"
                        " (default: from FreeBMD, checked against the transcription)")
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])

    conn = connect_readonly(path)
    try:
        plans = build_plans(conn, args.source, args.origin)
    finally:
        conn.close()

    changing = sum(1 for p in plans if p.new and not p.problem)
    skipped = sum(1 for p in plans if p.problem)
    with output_file("birth_index_media", "birth_register"):
        write_report(plans)
    print(f"{len(plans)} media; {changing} to update; {skipped} skipped")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0
    print(f"Applied: {apply(path, plans)} media updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
