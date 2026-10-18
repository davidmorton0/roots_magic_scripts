"""Move Ancestry death index citations to the Complex Website template.

For the Ancestry source (default 704, "Death Register - UK - Ancestry",
database "England & Wales, Civil Registration Death Index, 1916-2007", text
only), as decided on 2026-10-16 (D18, D19, D21):
  - the source moves to template 6 with Ancestry as the website; its text is
    set to --text and its comments are cleared;
  - each citation's transcription, in Ancestry's "Label: value" layout, is read
    and rewritten in the layout of FreeBMD's 1984+ entries: "Deaths <year>",
    then surname, given names, birth date, district, month of registration
    (MM.YY), and vol and page, or register, district and subdistrict, entry,
    separated by tabs; Ancestry's death age, inferred county and pasted source
    text are dropped;
  - fields:
      AccessDate    last-modified date of the citation's scan (a saved Ancestry page)
      SpecificItem  "entry for <given> <surname>, born <date>, <district>,
                    registered <month year>, vol. <v>, p. <p>" (or "register <r>,
                    district and subdistrict <d>, entry <e>")
      Citing        "General Register Office, England and Wales Civil Registration Indexes"
    and CitationName from them;
  - citations of the same entry on the same person are merged, as in
    freebmd_deaths.py.

Dry run by default: writes the proposed changes to
tmp/output/death_register/<timestamp>_ancestry_deaths.txt and changes nothing.
--apply writes them in one transaction; it refuses while any citation cannot
be read. RootsMagic must be closed, and the file must be a working copy.

Usage: python ancestry_deaths.py PATH_TO_RMTREE [--source ID] [--text TEXT]
           [--config FILE] [--apply]
"""

import argparse
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

from freebmd_deaths import Plan, access_date, citation_people, citation_scans, merge
from rmutils import (
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

DEFAULT_SOURCE = 704
DEFAULT_TEXT = ("England and Wales GRO death index entries, 1916-2007, transcribed in"
                " Ancestry's database (text only, no images)")
TEMPLATE_ID = 6
SOURCE_FIELDS = {
    "DatabaseCreator": "",
    "DatabaseTitle": "England & Wales, Civil Registration Death Index, 1916-2007",
    "Descriptor": "database",
    "WebsiteCreator": "Ancestry.com Operations",
    "WebsiteTitle": "Ancestry",
    "URL": "https://www.ancestry.co.uk",
}
CITATION_FIELDS = ("AccessDate", "SpecificItem", "Citing")
CITING = "General Register Office, England and Wales Civil Registration Indexes"
MONTHS = ("January February March April May June July August September"
          " October November December").split()
SHORT = {m[:3]: i for i, m in enumerate(MONTHS, 1)}
BORN = re.compile(r"^(\d{1,2}) (\w{3}) (\d{4})$")
REGISTERED = re.compile(r"^(\w{3}) (\d{4})$")


def labels(text: str) -> dict[str, str]:
    """Label (lower case) -> value from Ancestry's layout; the first of each label wins."""
    values = {}
    for line in (text or "").replace("\r", "").split("\n"):
        label, sep, value = line.partition(":")
        key = label.strip().lower()
        if sep and key and key not in values:
            values[key] = " ".join(value.split())
    return values


def plan_citation(cid: int, person: int, old_name: str, text: str,
                  scans: list[str], dates: dict[str, date]) -> Plan:
    plan = Plan(cid, person, old_name)
    v = labels(text)
    name = v.get("name", "").split()
    born = BORN.match(v.get("birth date", ""))
    registered = REGISTERED.match(v.get("registration date", ""))
    district = v.get("registration district", "")
    if len(name) < 2 or not born or not registered or not district:
        plan.problem = "transcription lacks Ancestry's name, birth date, registration date or district"
        return plan
    month = SHORT.get(registered.group(1).title())
    if not month or born.group(2).title() not in SHORT:
        plan.problem = "month not readable"
        return plan
    year = registered.group(2)
    if v.get("volume") and v.get("page"):
        ref_cols = [v["volume"], v["page"]]
        ref_text = f"vol. {v['volume']}, p. {v['page']}"
    elif v.get("register number") and v.get("district and subdistrict") and v.get("entry number"):
        ref_cols = [v["register number"], v["district and subdistrict"], v["entry number"]]
        ref_text = (f"register {v['register number']}, district and subdistrict"
                    f" {v['district and subdistrict']}, entry {v['entry number']}")
    else:
        plan.problem = "transcription has neither volume and page nor register, district and entry"
        return plan

    surname, given = name[-1], " ".join(name[:-1])
    birth = born.group(0)
    cols = [surname, given, birth, district, f"{month:02}.{year[2:]}", *ref_cols]
    plan.text = f"Deaths {year}\r\n" + "\t".join(cols)
    plan.key = (year, tuple(c.casefold() for c in cols))
    birth_text = (f"{int(born.group(1))} {MONTHS[SHORT[born.group(2).title()] - 1]}"
                  f" {born.group(3)}")
    plan.fields = {
        "AccessDate": access_date(scans, dates, plan),
        "SpecificItem": f"entry for {given} {surname}, born {birth_text}, {district},"
                        f" registered {MONTHS[month - 1]} {year}, {ref_text}",
        "Citing": CITING,
    }
    plan.name = "; ".join(plan.fields[f] for f in CITATION_FIELDS)
    return plan


def build_plans(conn: sqlite3.Connection, source_id: int, dates: dict[str, date]) -> list[Plan]:
    scans = citation_scans(conn, source_id)
    people = citation_people(conn, source_id)
    plans = []
    for cid, name, text in conn.execute(
        "SELECT CitationID, CitationName, ActualText FROM CitationTable WHERE SourceID = ?"
        " ORDER BY CitationID", (source_id,)
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


def write_report(source: tuple, text: str, plans: list[Plan], names: dict[int, str]) -> None:
    source_id, name, template_id, old_fields, old_text, old_comments = source
    problems = [p for p in plans if p.problem]
    merged = [p for p in plans if p.merge_into]
    print(f"Source S{source_id} '{name}'")
    print(f"   template: {template_id} -> {TEMPLATE_ID} (Complex Website)")
    print("   old fields: " + "; ".join(f"{k}={v!r}" for k, v in old_fields.items()))
    print("   new fields:")
    for key, value in SOURCE_FIELDS.items():
        print(f"      {key}: {value!r}")
    print(f"   text: {old_text!r} -> {text!r}")
    print(f"   comments: {len(old_comments or '')} characters -> cleared")
    print(f"\nCitations: {len(plans)}; cannot convert {len(problems)}; merged {len(merged)}")
    if problems:
        print("\n== Cannot convert (fix before --apply)")
        for p in problems:
            print(f"   C{p.citation_id} {p.old_name!r}: {p.problem}")
    issues = [p for p in plans if p.issues and not p.problem]
    if issues:
        print("\n== Issues (converted)")
        for p in issues:
            for issue in p.issues:
                print(f"   C{p.citation_id}: {issue}")
    if merged:
        print("\n== Duplicates merged")
        for p in merged:
            print(f"   C{p.citation_id} -> C{p.merge_into} {names.get(p.person, '?')} [P{p.person}]")
    print("\n== Proposed citation changes")
    for p in plans:
        if p.problem or p.merge_into:
            continue
        print(f"\nC{p.citation_id} {names.get(p.person, '?')} [P{p.person}]")
        for key in CITATION_FIELDS:
            print(f"   {key + ':':<14}{p.fields[key]}")
        print(f"   text:         {p.text!r}")


def apply(path: Path, source_id: int, text: str, plans: list[Plan]) -> tuple[int, int]:
    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    updated = merged = 0
    try:
        cur = conn.execute(
            "UPDATE SourceTable SET TemplateID = ?, Fields = ?, ActualText = ?, Comments = '',"
            " UTCModDate = ? WHERE SourceID = ?",
            (TEMPLATE_ID, fields_blob(SOURCE_FIELDS, declaration=False), text, stamp, source_id),
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
                (fields_blob(p.fields, declaration=False), p.name, p.text, stamp, p.citation_id, source_id),
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
    parser = argparse.ArgumentParser(prog="ancestry_deaths.py PATH_TO_RMTREE")
    parser.add_argument("--source", type=int, default=DEFAULT_SOURCE)
    parser.add_argument("--text", default=DEFAULT_TEXT, help="new source text")
    parser.add_argument("--config", type=Path, help="settings file (default config.toml)")
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])

    conn = connect_readonly(path)
    try:
        source = conn.execute(
            "SELECT SourceID, Name, TemplateID, Fields, ActualText, Comments FROM SourceTable"
            " WHERE SourceID = ?", (args.source,)
        ).fetchone()
        if source is None:
            print(f"Source S{args.source} not found")
            return 1
        expected = list(SOURCE_FIELDS) + list(CITATION_FIELDS)
        if sorted(name for name, _ in template_fields(conn, TEMPLATE_ID)) != sorted(expected):
            print(f"Template {TEMPLATE_ID} does not have the expected fields: {expected}")
            return 1
        dates = list_windows_file_dates(load_config(args.config)["scan_root"])
        source = (*source[:3], read_fields(source[3]), *source[4:])
        plans = build_plans(conn, args.source, dates)
        names = person_names(conn)
    finally:
        conn.close()

    problems = sum(1 for p in plans if p.problem)
    merged = sum(1 for p in plans if p.merge_into)
    with output_file("ancestry_deaths", "death_register"):
        write_report(source, args.text, plans, names)
    print(f"{len(plans)} citations; {len(plans) - problems - merged} to convert;"
          f" {merged} to merge; {problems} cannot convert")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0
    if problems:
        print("Not applied: fix the citations that cannot be converted first.")
        return 1
    updated, merged = apply(path, args.source, args.text, plans)
    print(f"Applied: source S{args.source}, {updated} citations updated, {merged} merged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
