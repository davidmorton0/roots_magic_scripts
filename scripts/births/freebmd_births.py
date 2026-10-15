"""Move FreeBMD birth index citations to the Complex Website template.

The source (ID 583, "Birth Register UK", renamed "Birth Register - UK - FreeBMD"
on 2026-10-15) uses a US birth-certificate template
with no fields for district, volume or page. This script moves the source to
RootsMagic's built-in template 6, "Complex Website (Multiple Articles or
Databases)" (Evidence Explained 4th ed., template 5), and fills each
citation's fields:
  SpecificItem  from its transcription (ActualText): FreeBMD or Ancestry
                layout, or the old Name and Certificate number fields when
                there is no transcription
  Citing        the printed GRO index quarter
  AccessDate    the last-modified date of the scan attached to the citation, read
                from Windows; blank when there is no scan or it is not on disk

Dry run by default: writes the proposed changes, and the issues to resolve
separately, to tmp/output/birth_register/<timestamp>_freebmd_births.txt and changes nothing.
--apply writes them in one transaction. It refuses while any citation cannot
be converted, so no citation is left with fields the new template cannot show.
RootsMagic must be closed, and the file must be a working copy.

Usage: python freebmd_births.py PATH_TO_RMTREE [--source ID] [--config FILE] [--apply]
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
    read_fields,
    template_fields,
    utc_mod_date,
)

DEFAULT_SOURCE = 583
TEMPLATE_ID = 6
OWNER_CITATION = 4
SOURCE_FIELDS = {
    "DatabaseCreator": "",
    "DatabaseTitle": "England & Wales Civil Registration Birth Index",
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
LAST_MONTH = {"March": "Mar", "June": "Jun", "September": "Sep", "December": "Dec"}
FIRST_MONTH = {"Jan": "Mar", "Apr": "Jun", "Jul": "Sep", "Oct": "Dec"}
HEAD = re.compile(r"^\s*Births\s+(Mar|Jun|Sep|Dec)\s+(\d{4})", re.IGNORECASE)
OLD_DATE = re.compile(r"(\w+)\s+(\d{4})\s*$")
YEAR = re.compile(r"\b(\d{4})\b")
UNCERTAIN_NOTE = re.compile(r"possible|duplicat|unsure|\?", re.IGNORECASE)


@dataclass
class Entry:
    surname: str
    given: str
    mother: str
    district: str
    volume: str
    page: str


@dataclass
class Plan:
    citation_id: int
    old_name: str
    fields: dict[str, str] = field(default_factory=dict)
    name: str = ""
    issues: list[str] = field(default_factory=list)
    problem: str = ""


def tidy(text: str) -> str:
    text = " ".join(text.split())
    return text.title() if text.isupper() else text


def parse_entry(tokens: list[str]) -> Entry | None:
    tokens = [t.strip() for t in tokens if t.strip()]
    if len(tokens) == 5:
        surname, given, district, volume, page = tokens
        mother = ""
    elif len(tokens) == 6:
        surname, given, mother, district, volume, page = tokens
    else:
        return None
    return Entry(tidy(surname), tidy(given), tidy(mother), tidy(district), volume, page)


def parse_freebmd(lines: list[str]) -> tuple[str, str, list[Entry]] | str:
    """(quarter, year, entries) from FreeBMD's layout, or a problem description."""
    head = HEAD.match(lines[0])
    quarter, year = head.group(1).title(), head.group(2)
    entries = []
    for i, line in enumerate(lines[1:], start=2):
        other = HEAD.match(line)
        if other:
            if (other.group(1).title(), other.group(2)) != (quarter, year):
                return "transcription holds entries from different quarters"
            continue
        entry = parse_entry(line.split("\t"))
        if entry is None:
            return f"transcription line {i} has an unexpected number of columns"
        entries.append(entry)
    return quarter, year, entries


def parse_ancestry(lines: list[str]) -> tuple[str, str, list[Entry]] | str:
    """(quarter, year, entries) from Ancestry's "Label: value" layout, or a problem."""
    values = {}
    for line in lines:
        label, sep, value = line.partition(":")
        if sep and label.strip() not in values:
            values[label.strip()] = value.strip()
    name = values.get("Name", "").split()
    quarter = FIRST_MONTH.get(values.get("Registration Quarter", "")[:3])
    year = YEAR.search(values.get("Registration Date", ""))
    needed = ("Registration District", "Volume Number", "Page Number")
    if len(name) < 2 or not quarter or not year or not all(values.get(k) for k in needed):
        return "transcription is in neither FreeBMD's nor Ancestry's layout"
    entry = Entry(
        tidy(name[-1]),
        tidy(" ".join(name[:-1])),
        tidy(values.get("Mother's Maiden Name", "")),
        tidy(values["Registration District"]),
        values["Volume Number"],
        values["Page Number"],
    )
    return quarter, year.group(1), [entry]


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


def plan_citation(
    citation_id: int,
    old_name: str,
    text: str,
    comments: str,
    old: dict[str, str],
    scans: list[str],
    dates: dict[str, date],
) -> Plan:
    plan = Plan(citation_id, old_name)
    lines = [
        line
        for line in (text or "").replace("\r", "").split("\n")
        if line.strip() and not line.strip().lower().startswith("http")
    ]

    if lines and HEAD.match(lines[0]):
        parsed = parse_freebmd(lines)
    elif lines:
        parsed = parse_ancestry(lines)
        if not isinstance(parsed, str):
            plan.issues.append(
                "transcription is from Ancestry, not FreeBMD; belongs under an Ancestry source"
            )
    else:
        when = OLD_DATE.search(old.get("Date", ""))
        quarter = LAST_MONTH.get(when.group(1)) if when else None
        entry = parse_entry(
            old.get("Name", "").split("\t") + old.get("CertificateNo", "").split("\t")
        )
        if entry and quarter:
            parsed = (quarter, when.group(2), [entry])
            plan.issues.append("no transcription; built from the old Name and Certificate number fields")
        else:
            parsed = "no transcription, and the old fields could not be read"
    if isinstance(parsed, str):
        plan.problem = parsed
        return plan
    quarter, year, entries = parsed

    first = entries[0]
    item = f"entry for {first.given} {first.surname}, {first.district}, vol. {first.volume}, p. {first.page}"
    if first.mother:
        item += f", mother's maiden name {first.mother}"
    for extra in entries[1:]:
        item += f"; also {extra.district}, vol. {extra.volume}, p. {extra.page}"
    if len(entries) > 1:
        plan.issues.append(f"transcription holds {len(entries)} entries")

    plan.fields = {
        "AccessDate": access_date(scans, dates, plan),
        "SpecificItem": item,
        "Citing": f"General Register Office, Births registered in {QUARTER_MONTHS[quarter]} {year}",
    }
    plan.name = "; ".join(plan.fields[name] for name in CITATION_FIELDS)

    if any("?" in e.page or "?" in e.volume for e in entries):
        plan.issues.append("volume or page contains '?'")

    def words(name: str) -> set[str]:
        return set(name.replace(".", " ").casefold().split())

    if old.get("Name") and words(old["Name"]) != words(f"{first.given} {first.surname}"):
        plan.issues.append(f"old Name field '{old['Name']}' differs from the index")
    if comments and UNCERTAIN_NOTE.search(comments):
        plan.issues.append(f"citation note: '{comments}'")
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


def build_plans(
    conn: sqlite3.Connection, source_id: int, dates: dict[str, date]
) -> list[Plan]:
    scans = citation_scans(conn, source_id)
    rows = conn.execute(
        "SELECT CitationID, CitationName, ActualText, Comments, Fields FROM CitationTable"
        " WHERE SourceID = ? ORDER BY CitationID",
        (source_id,),
    ).fetchall()
    return [
        plan_citation(cid, name or "", text or "", comments or "", read_fields(blob),
                      scans.get(cid, []), dates)
        for cid, name, text, comments, blob in rows
    ]


def write_report(source: tuple, plans: list[Plan]) -> None:
    source_id, name, template_id, old_fields = source
    problems = [p for p in plans if p.problem]
    with_issues = [p for p in plans if p.issues and not p.problem]

    print(f"Source S{source_id} '{name}'")
    print(f"   template: {template_id} -> {TEMPLATE_ID} (Complex Website)")
    print("   old fields: " + "; ".join(f"{k}={v!r}" for k, v in old_fields.items()))
    print("   new fields:")
    for key, value in SOURCE_FIELDS.items():
        print(f"      {key}: {value!r}")
    print(f"\nCitations: {len(plans)}; convert {len(plans) - len(problems)};"
          f" cannot convert {len(problems)}; with issues {len(with_issues)}")

    if problems:
        print("\n== Cannot convert (fix before --apply)")
        for p in problems:
            print(f"   C{p.citation_id} {p.old_name!r}: {p.problem}")
    if with_issues:
        print("\n== Issues to resolve separately (converted)")
        for p in with_issues:
            for issue in p.issues:
                print(f"   C{p.citation_id}: {issue}")
    print("\n== Proposed citation changes")
    for p in plans:
        if p.problem:
            continue
        print(f"\nC{p.citation_id}")
        print(f"   old name:     {p.old_name}")
        print(f"   AccessDate:   {p.fields['AccessDate']}")
        print(f"   SpecificItem: {p.fields['SpecificItem']}")
        print(f"   Citing:       {p.fields['Citing']}")


def apply(path: Path, source_id: int, plans: list[Plan]) -> None:
    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    try:
        cur = conn.execute(
            "UPDATE SourceTable SET TemplateID = ?, Fields = ?, UTCModDate = ? WHERE SourceID = ?",
            (TEMPLATE_ID, fields_blob(SOURCE_FIELDS, declaration=True), stamp, source_id),
        )
        if cur.rowcount != 1:
            raise RuntimeError(f"source S{source_id} not updated")
        for p in plans:
            cur = conn.execute(
                "UPDATE CitationTable SET Fields = ?, CitationName = ?, UTCModDate = ?"
                " WHERE CitationID = ? AND SourceID = ?",
                (fields_blob(p.fields, declaration=False), p.name, stamp, p.citation_id, source_id),
            )
            if cur.rowcount != 1:
                raise RuntimeError(f"citation C{p.citation_id} not updated")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="freebmd_births.py PATH_TO_RMTREE")
    parser.add_argument("--source", type=int, default=DEFAULT_SOURCE)
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
    finally:
        conn.close()

    problems = sum(1 for p in plans if p.problem)
    with output_file("freebmd_births", "birth_register"):
        write_report(source, plans)
    print(f"{len(plans)} citations; {len(plans) - problems} to convert; {problems} cannot convert")

    if not args.apply:
        print("Dry run: nothing changed.")
        return 0
    if problems:
        print("Not applied: fix the citations that cannot be converted first.")
        return 1
    apply(path, args.source, plans)
    print(f"Applied: source S{args.source} and {len(plans)} citations updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
