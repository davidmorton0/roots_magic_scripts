"""Move FreeBMD death index citations to the Complex Website template.

The source (default 589, "Death Register - UK - Freebmd") uses template 10003
"Death Registration, local level", whose fields hold mixed text. This script,
as was done for the FreeBMD birth index (freebmd_births.py):
  - renames the source (default "Death Register - UK - FreeBMD") and moves it
    to RootsMagic's built-in template 6, "Complex Website (Multiple Articles
    or Databases)", with FreeBMD as the website;
  - fills each citation's fields from its transcription (ActualText):
      AccessDate    last-modified date of the citation's scan, read from Windows
      SpecificItem  "entry for <given> <surname>, age <n>, <district>, vol. <v>, p. <p>"
                    (before 1866: no age; mid 1969-1983: "born <date>"; 1984 on:
                    "born <date>, <district>, registered <month year>, ...")
      Citing        "General Register Office, Deaths registered in <months> <year>"
                    (1984 on: "... Deaths registered in <year>")
    and rebuilds CitationName from them;
  - rewrites the transcription in FreeBMD's layout: the heading line, then one
    line per entry with the columns separated by single tabs, lines by CR LF;
    spaces around columns, empty columns and full stops after whole names
    ("William." -> "William"; initials keep theirs) are removed;
  - merges citations of the same entry on the same person (one was made for
    each fact it was linked to): the lowest CitationID is kept, the others'
    citation and media links move to it unless it has them already, and the
    others are deleted with their remaining links.
Names, districts, volumes and pages are taken as printed; names and districts
in capitals are written in title case in SpecificItem only.

Dry run by default: writes the proposed changes, and the issues to resolve
separately, to tmp/output/death_register/<timestamp>_freebmd_deaths.txt and
changes nothing. --apply writes them in one transaction. It refuses while any
citation cannot be read. RootsMagic must be closed, and the file must be a
working copy.

Usage: python freebmd_deaths.py PATH_TO_RMTREE [--source ID] [--name NAME]
           [--config FILE] [--apply]
"""

import argparse
import re
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from rmutils import (
    access_date_text,
    connect_readonly,
    connect_readwrite,
    db_path_arg,
    fields_blob,
    list_windows_file_dates,
    load_config,
    output_file,
    person_names,
    read_fields,
    template_fields,
    utc_mod_date,
)

DEFAULT_SOURCE = 589
DEFAULT_NAME = "Death Register - UK - FreeBMD"
TEMPLATE_ID = 6
OWNER_EVENT, OWNER_CITATION = 2, 4
SOURCE_FIELDS = {
    "DatabaseCreator": "",
    "DatabaseTitle": "England & Wales Civil Registration Death Index",
    "Descriptor": "database with images",
    "WebsiteCreator": "Free UK Genealogy",
    "WebsiteTitle": "FreeBMD",
    "URL": "https://www.freebmd.org.uk",
}
CITATION_FIELDS = ("AccessDate", "SpecificItem", "Citing")

QUARTER_MONTHS = {
    "Mar": "January, February, and March",
    "Jun": "April, May, and June",
    "Sep": "July, August, and September",
    "Dec": "October, November, and December",
}
MONTHS = ("January February March April May June July August September"
          " October November December").split()
INDEX_MONTHS = {m: i for i, m in enumerate("JA FE MR AP MY JE JY AU SE OC NO DE".split(), 1)}
HEAD = re.compile(r"^Deaths\s+(?:(Mar|Jun|Sep|Dec)\s+)?(\d{4})$", re.IGNORECASE)
BORN = re.compile(r"^(\d{1,2})\s+([A-Za-z]{2})\s+(\d{4})$")
ABOUT = re.compile(r"^about\s+(\d{4})$", re.IGNORECASE)
REGISTERED = re.compile(r"^(\d\d)\.(\d\d)$")


@dataclass
class Entry:
    surname: str
    given: str
    age: str  # age, or birth date as printed; "" before 1866
    district: str
    registered: str  # "MM.YY", 1984 on; else ""
    volume: str
    page: str


@dataclass
class Plan:
    citation_id: int
    person: int
    old_name: str
    text: str = ""
    entries: list[Entry] = field(default_factory=list)
    key: tuple = ()
    fields: dict[str, str] = field(default_factory=dict)
    name: str = ""
    merge_into: int = 0
    issues: list[str] = field(default_factory=list)
    problem: str = ""


def tidy(text: str) -> str:
    text = " ".join(text.split())
    return text.title() if text.isupper() else text


def drop_name_stops(name: str) -> str:
    """'William.' -> 'William'; an initial ('T.') keeps its stop."""
    return " ".join(w[:-1] if w.endswith(".") and len(w) > 2 else w for w in name.split())


def columns(line: str, year: int) -> list[str]:
    """The entry's columns: tab-separated, or (if typed with spaces) split by position."""
    cols = [c.strip() for c in line.split("\t") if c.strip()]
    if len(cols) > 1:
        return cols
    words = line.split()
    if year < 1866 or len(words) < 5:
        return words
    # surname, given words, age or birth date, district words, volume, page
    for i in range(2, len(words) - 2):
        if words[i].isdigit() or words[i].lower() == "about":
            born = " ".join(words[i:i + 3])
            if BORN.match(born):
                return [words[0], " ".join(words[1:i]), born, " ".join(words[i + 3:-2]), *words[-2:]]
            if words[i].lower() == "about":
                return [words[0], " ".join(words[1:i]), " ".join(words[i:i + 2]),
                        " ".join(words[i + 2:-2]), *words[-2:]]
            return [words[0], " ".join(words[1:i]), words[i], " ".join(words[i + 1:-2]), *words[-2:]]
    return words


def parse_entry(cols: list[str], year: int) -> Entry | str:
    expected = 7 if year >= 1984 else 6 if year >= 1866 else 5
    if len(cols) != expected:
        return f"{len(cols)} columns, expected {expected}: {cols}"
    if expected == 5:
        surname, given, district, volume, page = cols
        age = registered = ""
    elif expected == 6:
        surname, given, age, district, volume, page = cols
        registered = ""
    else:
        surname, given, age, district, registered, volume, page = cols
        match = REGISTERED.match(registered)
        if not match or int(match.group(1)) not in range(1, 13) or int(match.group(2)) != year % 100:
            return f"registration column {registered!r} does not fit {year}"
    if expected >= 6 and not (age.isdigit() or BORN.match(age) or ABOUT.match(age)):
        return f"age or birth date {age!r} not readable"
    if year >= 1970 and age.isdigit():  # birth dates from the Jun 1969 quarter
        return f"age {age!r} where the index gives a birth date"
    return Entry(drop_name_stops(surname), drop_name_stops(given), age, district,
                 registered, volume, page)


def age_text(entry: Entry) -> str:
    if not entry.age:
        return ""
    if entry.age.isdigit():
        return f"age {entry.age}"
    about = ABOUT.match(entry.age)
    if about:
        return f"born about {about.group(1)}"
    day, month, year = BORN.match(entry.age).groups()
    return f"born {int(day)} {MONTHS[INDEX_MONTHS[month.upper()] - 1]} {year}"


def specific_item(entry: Entry) -> str:
    parts = [f"entry for {tidy(entry.given)} {tidy(entry.surname)}"]
    if entry.age:
        parts.append(age_text(entry))
    parts.append(tidy(entry.district))
    if entry.registered:
        month, year = REGISTERED.match(entry.registered).groups()
        parts.append(f"registered {MONTHS[int(month) - 1]} 19{year}")
    parts.append(f"vol. {entry.volume}")
    parts.append(f"p. {entry.page}")
    return ", ".join(parts)


def access_date(scans: list[str], dates: dict[str, date], plan: Plan) -> str:
    """Last-modified date of the citation's scan as 'D Month YYYY', or '' with an issue noted."""
    if not scans:
        plan.issues.append("no scan attached; access date left blank")
        return ""
    found = []
    for scan in scans:
        modified = dates.get(scan.lower())
        if modified is None:
            plan.issues.append(f"scan not found on disk: {scan}")
        else:
            found.append(modified)
    if not found:
        plan.issues.append("access date left blank")
        return ""
    if len(set(found)) > 1:
        plan.issues.append("scans have different last-modified dates; earliest used")
    return access_date_text(min(found))


def plan_citation(cid: int, person: int, old_name: str, text: str,
                  scans: list[str], dates: dict[str, date]) -> Plan:
    plan = Plan(cid, person, old_name)
    lines = [
        line.strip()
        for line in (text or "").replace("\r", "").split("\n")
        if line.strip() and not line.strip().lower().startswith("http")
    ]
    head = HEAD.match(lines[0]) if lines else None
    if not head:
        plan.problem = "transcription is not in FreeBMD's layout ('Deaths <quarter> <year>')"
        return plan
    quarter, year = (head.group(1) or "").title(), int(head.group(2))
    if (year >= 1984) != (not quarter):
        plan.problem = f"heading {lines[0]!r}: quarterly before 1984, yearly from 1984"
        return plan
    for line in lines[1:]:
        if HEAD.match(line):
            plan.problem = "transcription holds more than one heading"
            return plan
        entry = parse_entry(columns(line, year), year)
        if isinstance(entry, str):
            plan.problem = entry
            return plan
        plan.entries.append(entry)
    if not plan.entries:
        plan.problem = "transcription has no entry"
        return plan

    heading = f"Deaths {quarter} {year}" if quarter else f"Deaths {year}"
    rows = [
        "\t".join(c for c in (e.surname, e.given, e.age, e.district, e.registered, e.volume, e.page) if c)
        for e in plan.entries
    ]
    plan.text = "\r\n".join([heading, *rows])
    plan.key = (heading, tuple(r.casefold() for r in rows))

    item = specific_item(plan.entries[0])
    for extra in plan.entries[1:]:
        item += f"; also {tidy(extra.district)}, vol. {extra.volume}, p. {extra.page}"
    if len(plan.entries) > 1:
        plan.issues.append(f"transcription holds {len(plan.entries)} entries")
    months = QUARTER_MONTHS[quarter] + " " if quarter else ""
    plan.fields = {
        "AccessDate": access_date(scans, dates, plan),
        "SpecificItem": item,
        "Citing": f"General Register Office, Deaths registered in {months}{year}",
    }
    plan.name = "; ".join(plan.fields[name] for name in CITATION_FIELDS)
    if any("?" in e.page or "?" in e.volume or "[" in e.age for e in plan.entries):
        plan.issues.append("age, volume or page is uncertain ('?' or '[')")
    return plan


def citation_scans(conn: sqlite3.Connection, source_id: int) -> dict[int, list[str]]:
    scans = defaultdict(list)
    for cid, path, file in conn.execute(
        """SELECT ml.OwnerID, m.MediaPath, m.MediaFile
           FROM MediaLinkTable ml JOIN MultimediaTable m USING (MediaID)
           WHERE ml.OwnerType = ?
             AND ml.OwnerID IN (SELECT CitationID FROM CitationTable WHERE SourceID = ?)
           ORDER BY ml.OwnerID, m.MediaID""",
        (OWNER_CITATION, source_id),
    ):
        scans[cid].append(f"{(path or '').rstrip(chr(92))}\\{file or ''}")
    return scans


def citation_people(conn: sqlite3.Connection, source_id: int) -> dict[int, set[int]]:
    """Citation -> the people it is linked to (directly or through their events)."""
    people = defaultdict(set)
    for cid, otype, oid, event_owner_type, event_owner in conn.execute(
        """SELECT cl.CitationID, cl.OwnerType, cl.OwnerID, e.OwnerType, e.OwnerID
           FROM CitationLinkTable cl
           LEFT JOIN EventTable e ON cl.OwnerType = 2 AND e.EventID = cl.OwnerID
           WHERE cl.CitationID IN (SELECT CitationID FROM CitationTable WHERE SourceID = ?)""",
        (source_id,),
    ):
        if otype == 0:
            people[cid].add(oid)
        elif otype == OWNER_EVENT and event_owner_type == 0:
            people[cid].add(event_owner)
        else:
            people[cid].add(-1)  # a family, or an event that is missing
    return people


def build_plans(conn: sqlite3.Connection, source_id: int, dates: dict[str, date]) -> list[Plan]:
    scans = citation_scans(conn, source_id)
    people = citation_people(conn, source_id)
    plans = []
    for cid, name, text in conn.execute(
        "SELECT CitationID, CitationName, ActualText FROM CitationTable"
        " WHERE SourceID = ? ORDER BY CitationID",
        (source_id,),
    ):
        linked = people.get(cid, set())
        person = next(iter(linked)) if len(linked) == 1 else 0
        plan = plan_citation(cid, person, name or "", text or "", scans.get(cid, []), dates)
        if not linked:
            plan.issues.append("not linked to anything")
        elif len(linked) > 1 or person < 0:
            plan.issues.append("linked to more than one person, or not to a person; not merged")
        plans.append(plan)

    groups = defaultdict(list)
    for p in plans:
        if not p.problem and p.person > 0:
            groups[(p.person, p.key)].append(p)
    for group in groups.values():
        for p in group[1:]:
            p.merge_into = group[0].citation_id
    return plans


def write_report(source: tuple, new_name: str, plans: list[Plan], names: dict[int, str]) -> None:
    source_id, name, template_id, old_fields = source
    problems = [p for p in plans if p.problem]
    with_issues = [p for p in plans if p.issues and not p.problem]
    merged = [p for p in plans if p.merge_into]

    print(f"Source S{source_id} '{name}'")
    print(f"   name: '{name}' -> '{new_name}'")
    print(f"   template: {template_id} -> {TEMPLATE_ID} (Complex Website)")
    print("   old fields: " + "; ".join(f"{k}={v!r}" for k, v in old_fields.items()))
    print("   new fields:")
    for key, value in SOURCE_FIELDS.items():
        print(f"      {key}: {value!r}")
    print(f"\nCitations: {len(plans)}; cannot convert {len(problems)};"
          f" merged into another {len(merged)}; kept {len(plans) - len(problems) - len(merged)};"
          f" with issues {len(with_issues)}")

    if problems:
        print("\n== Cannot convert (fix before --apply)")
        for p in problems:
            print(f"   C{p.citation_id} {p.old_name!r}: {p.problem}")
    if with_issues:
        print("\n== Issues to resolve separately (converted)")
        for p in with_issues:
            for issue in p.issues:
                print(f"   C{p.citation_id}: {issue}")
    if merged:
        print("\n== Duplicates merged (links and scans moved to the kept citation, then deleted)")
        for p in merged:
            print(f"   C{p.citation_id} -> C{p.merge_into}"
                  f" {names.get(p.person, '?')} [P{p.person}]")
    print("\n== Proposed citation changes")
    for p in plans:
        if p.problem or p.merge_into:
            continue
        print(f"\nC{p.citation_id} {names.get(p.person, '?')} [P{p.person}]")
        print(f"   old name:     {p.old_name}")
        print(f"   AccessDate:   {p.fields['AccessDate']}")
        print(f"   SpecificItem: {p.fields['SpecificItem']}")
        print(f"   Citing:       {p.fields['Citing']}")
        print(f"   text:         {p.text!r}")


def merge(conn: sqlite3.Connection, plan: Plan, stamp: float) -> None:
    keep, gone = plan.merge_into, plan.citation_id
    have = set(conn.execute(
        "SELECT OwnerType, OwnerID FROM CitationLinkTable WHERE CitationID = ?", (keep,)))
    for link_id, otype, oid in conn.execute(
        "SELECT LinkID, OwnerType, OwnerID FROM CitationLinkTable WHERE CitationID = ?", (gone,)
    ).fetchall():
        if (otype, oid) in have:
            conn.execute("DELETE FROM CitationLinkTable WHERE LinkID = ?", (link_id,))
        else:
            conn.execute("UPDATE CitationLinkTable SET CitationID = ?, UTCModDate = ? WHERE LinkID = ?",
                         (keep, stamp, link_id))
            have.add((otype, oid))
    media = {m for (m,) in conn.execute(
        "SELECT MediaID FROM MediaLinkTable WHERE OwnerType = ? AND OwnerID = ?", (OWNER_CITATION, keep))}
    for link_id, mid in conn.execute(
        "SELECT LinkID, MediaID FROM MediaLinkTable WHERE OwnerType = ? AND OwnerID = ?",
        (OWNER_CITATION, gone),
    ).fetchall():
        if mid in media:
            conn.execute("DELETE FROM MediaLinkTable WHERE LinkID = ?", (link_id,))
        else:
            conn.execute("UPDATE MediaLinkTable SET OwnerID = ?, UTCModDate = ? WHERE LinkID = ?",
                         (keep, stamp, link_id))
            media.add(mid)
    cur = conn.execute("DELETE FROM CitationTable WHERE CitationID = ?", (gone,))
    if cur.rowcount != 1:
        raise RuntimeError(f"citation C{gone} not deleted")


def apply(path: Path, source_id: int, new_name: str, plans: list[Plan]) -> tuple[int, int]:
    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    updated = merged = 0
    try:
        cur = conn.execute(
            "UPDATE SourceTable SET Name = ?, TemplateID = ?, Fields = ?, UTCModDate = ?"
            " WHERE SourceID = ?",
            (new_name, TEMPLATE_ID, fields_blob(SOURCE_FIELDS, declaration=False), stamp, source_id),
        )
        if cur.rowcount != 1:
            raise RuntimeError(f"source S{source_id} not updated")
        for p in plans:
            if p.merge_into:
                merge(conn, p, stamp)
                merged += 1
                continue
            cur = conn.execute(
                "UPDATE CitationTable SET Fields = ?, CitationName = ?, ActualText = ?, UTCModDate = ?"
                " WHERE CitationID = ? AND SourceID = ?",
                (fields_blob(p.fields, declaration=False), p.name, p.text, stamp,
                 p.citation_id, source_id),
            )
            if cur.rowcount != 1:
                raise RuntimeError(f"citation C{p.citation_id} not updated")
            updated += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return updated, merged


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="freebmd_deaths.py PATH_TO_RMTREE")
    parser.add_argument("--source", type=int, default=DEFAULT_SOURCE)
    parser.add_argument("--name", default=DEFAULT_NAME, help="new source name")
    parser.add_argument("--config", type=Path, help="settings file (default config.toml)")
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])

    conn = connect_readonly(path)
    try:
        source = conn.execute(
            "SELECT SourceID, Name, TemplateID, Fields FROM SourceTable WHERE SourceID = ?",
            (args.source,),
        ).fetchone()
        if source is None:
            print(f"Source S{args.source} not found")
            return 1
        expected = list(SOURCE_FIELDS) + list(CITATION_FIELDS)
        if sorted(name for name, _ in template_fields(conn, TEMPLATE_ID)) != sorted(expected):
            print(f"Template {TEMPLATE_ID} does not have the expected fields: {expected}")
            return 1
        dates = list_windows_file_dates(load_config(args.config)["scan_root"])
        source = (*source[:3], read_fields(source[3]))
        plans = build_plans(conn, args.source, dates)
        names = person_names(conn)
    finally:
        conn.close()

    problems = sum(1 for p in plans if p.problem)
    merged = sum(1 for p in plans if p.merge_into)
    with output_file("freebmd_deaths", "death_register"):
        write_report(source, args.name, plans, names)
    print(f"{len(plans)} citations; {len(plans) - problems - merged} to convert;"
          f" {merged} to merge; {problems} cannot convert")

    if not args.apply:
        print("Dry run: nothing changed.")
        return 0
    if problems:
        print("Not applied: fix the citations that cannot be converted first.")
        return 1
    updated, merged = apply(path, args.source, args.name, plans)
    print(f"Applied: source S{args.source}, {updated} citations updated, {merged} merged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
