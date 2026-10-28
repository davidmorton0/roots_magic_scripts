"""Fetch citations and flag what does not fit the citation standards and citation forms (read-only).

The standards and the "Citation forms" table are in .claude/skills/rm-evaluate-source/source_types.md
(--types FILE for another). Each citation takes the form of the first row whose Name matches its
source's name, then is checked:

  FORM     a citation field does not have the form's shape
  EMPTY    a citation field is empty (template 6: SpecificItem, Citing; free-form: Page)
  C1       CitationName differs from the citation fields joined with "; " in template order, an empty
           field as an empty part (free-form: Page)
  G16      AccessDate empty while the citation has scans (the file date: files/file.py info)
  C3       AccessDate not written as "7 August 2020"
  G10      transcription empty; a tab after a label; not in the form's layout (index or labels)
  C2       transcription lines end with LF only, not CR LF
  LAST     the transcription's last line does not have the form's shape (e.g. the FreeBMD link)
  G11      another citation of the same source has the same entry (SpecificItem, or Page)
  G12      shares a scan with another citation of the same source linked to the same person
  UNUSED   linked to nothing

Flags are for review: the user decides what to change. Sources on templates other than 0 and 6
get only C1, G10, C2, G12 and UNUSED (their template is a source issue: evaluate_source.py; their
fields, e.g. a newspaper's page number, do not identify an entry, so G11 is not checked).

Writes each flagged citation (every one with --citation) to
tmp/output/citations/<timestamp>_evaluate_citation.txt and prints the counts per source and flag.

Usage: python evaluate_citation.py PATH_TO_RMTREE (--source ID ... | --citation ID ... | --all) [--types FILE]
"""

import argparse
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from rmutils import (
    PROJECT_DIR,
    connect_readonly,
    db_path_arg,
    field_values,
    markdown_table,
    name_patterns,
    output_file,
    read_fields,
    template_fields,
    wildcard,
)

TYPES_FILE = PROJECT_DIR / ".claude" / "skills" / "rm-evaluate-source" / "source_types.md"
OWNER_PERSON, OWNER_FAMILY, OWNER_EVENT, OWNER_NAME = 0, 1, 2, 7
OWNER_MEDIA_CITATION = 4
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
ACCESS_DATE = re.compile(rf"\d{{1,2}} ({MONTHS}) \d{{4}}")
INDEX_HEADER = re.compile(r"(Births|Deaths|Marriages)( \w{3})? \d{4}\b.*")  # FreeBMD may add "  (>99%)"
LABEL = re.compile(r"[^\t:]+: \S")
TAB_AFTER_LABEL = re.compile(r"^[^\t:]+:\t", re.MULTILINE)


@dataclass
class CitationForm:
    name: str
    patterns: list[re.Pattern]
    fields: dict[str, list[re.Pattern]]
    layout: str
    last: re.Pattern | None


@dataclass
class Citation:
    cid: int
    sid: int
    source: str
    template: int
    order: list[str]
    fields: dict[str, str]
    name: str
    text: str
    links: int
    people: set[int]
    scans: list[tuple[int, str]]
    form: CitationForm | None = None
    flags: list[str] = field(default_factory=list)


def load_forms(path: Path) -> list[CitationForm]:
    forms = []
    for row in markdown_table(path, "Citation forms"):
        last = row["Last line"].strip("`")
        forms.append(CitationForm(
            row["Form"], name_patterns(row["Name"]),
            {name: [wildcard(v) for v in values] for name, values in field_values(row["Fields"]).items()},
            row["Transcription"], None if last == "-" else wildcard(last)))
    return forms


def people_of(conn, links: list[tuple[int, int]]) -> set[int]:
    """People a citation's links touch: a person, a name's person, an event's person or family partners."""
    people = set()
    for otype, oid in links:
        if otype == OWNER_PERSON:
            people.add(oid)
        elif otype == OWNER_NAME:
            people |= {r[0] for r in conn.execute("SELECT OwnerID FROM NameTable WHERE NameID = ?", (oid,))}
        elif otype == OWNER_EVENT:
            row = conn.execute("SELECT OwnerType, OwnerID FROM EventTable WHERE EventID = ?", (oid,)).fetchone()
            if row:
                people |= people_of(conn, [row])
        elif otype == OWNER_FAMILY:
            row = conn.execute("SELECT FatherID, MotherID FROM FamilyTable WHERE FamilyID = ?", (oid,)).fetchone()
            people |= {p for p in row or () if p}
    return people


def load_citations(conn, source_ids: list[int]) -> list[Citation]:
    orders = {}
    citations = []
    for sid in source_ids:
        source, template = conn.execute("SELECT Name, TemplateID FROM SourceTable WHERE SourceID = ?",
                                        (sid,)).fetchone()
        if template not in orders:
            orders[template] = [n for n, is_cit in template_fields(conn, template) if is_cit] if template else ["Page"]
        for cid, blob, name, text in conn.execute(
                "SELECT CitationID, Fields, CitationName, ActualText FROM CitationTable WHERE SourceID = ?"
                " ORDER BY CitationID", (sid,)):
            links = conn.execute("SELECT OwnerType, OwnerID FROM CitationLinkTable WHERE CitationID = ?",
                                 (cid,)).fetchall()
            scans = [(mid, f"{p}\\{f}") for mid, p, f in conn.execute(
                "SELECT m.MediaID, m.MediaPath, m.MediaFile FROM MediaLinkTable l JOIN MultimediaTable m USING"
                " (MediaID) WHERE l.OwnerType = ? AND l.OwnerID = ? ORDER BY m.MediaID", (OWNER_MEDIA_CITATION, cid))]
            citations.append(Citation(cid, sid, source or "", template, orders[template], read_fields(blob),
                                      name or "", text or "", len(links), people_of(conn, links), scans))
    return citations


def evaluate(c: Citation, same_source: list[Citation]) -> None:
    flag = c.flags.append
    form = c.form
    if c.template in (0, 6):
        required = ["Page"] if c.template == 0 else ["SpecificItem", "Citing"]
        for name in required:
            if not c.fields.get(name, "").strip():
                flag(f"EMPTY {name} is empty")
        if form:
            for name, patterns in form.fields.items():
                value = c.fields.get(name, "")
                if value and not any(p.fullmatch(value) for p in patterns):
                    shapes = " or ".join(repr(p.pattern.replace("(.+?)", "*").replace("\\", "")) for p in patterns)
                    flag(f"FORM {name} {value!r} does not have the shape {shapes}")
        if c.template == 6:
            access = c.fields.get("AccessDate", "")
            if not access and c.scans:
                flag(f"G16 AccessDate empty; {len(c.scans)} scan(s): take the file date (files/file.py info)")
            elif access and not ACCESS_DATE.fullmatch(access):
                flag(f"C3 AccessDate {access!r} not written as '7 August 2020'")

    expected = "; ".join(c.fields.get(n, "") for n in c.order)
    if c.order and c.name != expected:
        flag(f"C1 CitationName {c.name!r}; fields give {expected!r}")

    text = c.text
    lines = text.replace("\r\n", "\n").split("\n")
    if not text.strip():
        flag("G10 transcription is empty")
    else:
        if re.search(r"(?<!\r)\n", text):
            flag("C2 transcription lines end with LF only")
        if TAB_AFTER_LABEL.search(text.replace("\r\n", "\n")):
            flag("G10 a tab after a label")
        if form and form.layout == "index" and not (INDEX_HEADER.fullmatch(lines[0].strip())
                                                    and any("\t" in line for line in lines[1:])):
            flag(f"G10 not in the index layout (header line, then tab-separated entries): {lines[0]!r}")
        if form and form.layout == "labels" and not LABEL.match(lines[0]):
            flag(f"G10 does not start with a 'Label: value' line: {lines[0][:60]!r}")
        if form and form.last and not form.last.fullmatch(lines[-1].strip()):
            flag(f"LAST last line {lines[-1][:60]!r} does not have the shape"
                 f" {form.last.pattern.replace('(.+?)', '*').replace(chr(92), '')!r}")

    key = " ".join((c.fields.get("SpecificItem") or c.fields.get("Page") or "").split()).casefold()
    if key and c.template in (0, 6):
        same = [o for o in same_source if o.cid != c.cid
                and " ".join((o.fields.get("SpecificItem") or o.fields.get("Page") or "").split()).casefold() == key]
        if same:
            flag("G11 same entry as " + ", ".join(f"C{o.cid}" for o in same))
    shared = sorted({o.cid for o in same_source if o.cid != c.cid and c.people & o.people
                     and {m for m, _ in c.scans} & {m for m, _ in o.scans}})
    if shared:
        flag("G12 shares a scan and a person with " + ", ".join(f"C{cid}" for cid in shared))
    if not c.links:
        flag("UNUSED linked to nothing")


def report(c: Citation) -> None:
    print(f"C{c.cid}  S{c.sid} '{c.source}'  form: {c.form.name if c.form else 'none'}")
    for name, value in c.fields.items():
        print(f"   field {name}: {value!r}")
    print(f"   CitationName: {c.name!r}")
    print(f"   links {c.links}, people {sorted(c.people)}, scans: " + (", ".join(f"M{m} {p}" for m, p in c.scans)
                                                                      or "none"))
    for line in c.text.replace("\r\n", "\n").split("\n")[:4]:
        print(f"   | {line}")
    for flag in c.flags or ["(no flags)"]:
        print(f"   ! {flag}")
    print()


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="evaluate_citation.py PATH_TO_RMTREE")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--source", type=int, action="append")
    which.add_argument("--citation", type=int, action="append")
    which.add_argument("--all", action="store_true")
    parser.add_argument("--types", type=Path, default=TYPES_FILE)
    args = parser.parse_args(sys.argv[2:])
    forms = load_forms(args.types)

    conn = connect_readonly(path)
    try:
        if args.all:
            source_ids = [r[0] for r in conn.execute("SELECT SourceID FROM SourceTable ORDER BY SourceID")]
        elif args.source:
            source_ids = args.source
        else:
            source_ids = sorted({r[0] for cid in args.citation for r in conn.execute(
                "SELECT SourceID FROM CitationTable WHERE CitationID = ?", (cid,))})
        known = {r[0] for r in conn.execute("SELECT SourceID FROM SourceTable")}
        missing = [f"S{s}" for s in source_ids if s not in known]
        if args.citation:
            found = {r[0] for r in conn.execute("SELECT CitationID FROM CitationTable")}
            missing += [f"C{c}" for c in args.citation if c not in found]
        if missing:
            print("Not found: " + ", ".join(missing))
            return 1
        citations = load_citations(conn, source_ids)
    finally:
        conn.close()

    by_source = defaultdict(list)
    for c in citations:
        c.form = next((f for f in forms if any(p.fullmatch(c.source) for p in f.patterns)), None)
        by_source[c.sid].append(c)
    for c in citations:
        evaluate(c, by_source[c.sid])
    chosen = [c for c in citations if c.cid in set(args.citation)] if args.citation else citations

    with output_file("evaluate_citation", "citations"):
        print(f"File: {path}\nTypes: {args.types}\n")
        for c in chosen:
            if c.flags or args.citation:
                report(c)
    for sid, group in by_source.items():
        mine = [c for c in group if c in chosen]
        if not mine:
            continue
        counts = Counter(flag.split()[0] for c in mine for flag in c.flags)
        form = mine[0].form.name if mine[0].form else "no form"
        print(f"S{sid} '{mine[0].source}' [{form}]: {len(mine)} citations, {sum(1 for c in mine if c.flags)} flagged"
              + ("; " + ", ".join(f"{code} {n}" for code, n in sorted(counts.items())) if counts else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
