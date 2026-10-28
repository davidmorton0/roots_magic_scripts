"""Fetch sources and flag what does not fit the source standards and the source-type table (read-only).

The table and standards are in .claude/skills/rm-evaluate-source/source_types.md (--types FILE for
another). Each source is matched to a source type by its name and template, then checked:

  TYPE     no source type matches the name
  G1       template differs from the type's (no type: template neither 0 nor 6); the type's
           Required, Fixed and Text columns are then not checked
  G2       name not "<Record> - <Country> - <Provider>" (checked only when no type matches),
           or spaces at either end or two together
  G3       another source with the same name, or (template 6) the same database and website title
  G4       source text empty, or holding a URL; comments not empty (check for pasted website text)
  G18      template 6 with citation scans in a Newspaper folder (the newspaper may be the source)
  L1       Fields saved with a byte-order mark or XML declaration
  L2       a required source field empty (the template's, and the type's Required column);
           DatabaseCreator filled on template 6
  L3       no citations
  FIXED    a field differs from the type's Fixed value
  TEXT     source text differs from the type's Text

Flags are for review: the skill's user decides what to change. G5 (owner and title as shown when
accessed) is not checked; the fields are printed for comparison with the saved page.

Writes each source's data and flags to tmp/output/sources/<timestamp>_evaluate_source.txt and
prints one line per source (--source) or the counts per flag (--all).

Usage: python evaluate_source.py PATH_TO_RMTREE (--source ID [--source ID ...] | --all) [--types FILE]
"""

import argparse
import re
import sys
from collections import Counter
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
)

TYPES_FILE = PROJECT_DIR / ".claude" / "skills" / "rm-evaluate-source" / "source_types.md"
OWNER_CITATION = 4
WEBSITE_REQUIRED = ["DatabaseTitle", "Descriptor", "WebsiteTitle", "URL"]
FREE_FORM_REQUIRED = ["Footnote", "ShortFootnote", "Bibliography"]
COUNTRIES = {"uk", "britain", "england", "scotland", "wales", "ireland", "us", "usa", "china", "international"}
URL_TEXT = re.compile(r"https?://|www\.", re.IGNORECASE)


@dataclass
class SourceType:
    name: str
    patterns: list[re.Pattern]
    template: int
    required: list[str]
    fixed: dict[str, list[str]]
    text: str | None

    def match(self, source_name: str) -> re.Match | None:
        return next((m for p in self.patterns if (m := p.fullmatch(source_name))), None)


@dataclass
class Source:
    sid: int
    name: str
    template: int
    template_name: str
    fields: dict[str, str]
    text: str
    comments: str
    declared: bool
    citations: int
    links: int
    scans: list[str]
    kind: SourceType | None = None
    capture: str = ""
    flags: list[str] = field(default_factory=list)


def load_types(path: Path) -> list[SourceType]:
    """Rows of the table under '## Source types'."""
    return [
        SourceType(row["Type"], name_patterns(row["Name"]), int(row["Template"]),
                   [r.strip() for r in row["Required"].split(",") if r.strip()], field_values(row["Fixed"]),
                   None if row["Text"] == "-" else row["Text"])
        for row in markdown_table(path, "Source types")
    ]


def choose_type(source: Source, types: list[SourceType]) -> None:
    matches = [(t, m) for t in types if (m := t.match(source.name))]
    best = next(((t, m) for t, m in matches if t.template == source.template), matches[0] if matches else None)
    if best:
        source.kind = best[0]
        source.capture = best[1].group(1) if best[1].groups() else ""


def fill(value: str, capture: str) -> str:
    return value.replace("{1}", capture)


def load_sources(conn, ids: list[int] | None) -> list[Source]:
    templates = dict(conn.execute("SELECT TemplateID, Name FROM SourceTemplateTable"))
    sql = "SELECT SourceID, Name, TemplateID, Fields, ActualText, Comments FROM SourceTable"
    rows = conn.execute(sql + " ORDER BY SourceID").fetchall() if ids is None else \
        [r for i in ids if (r := conn.execute(sql + " WHERE SourceID = ?", (i,)).fetchone())]
    sources = []
    for sid, name, template, blob, text, comments in rows:
        raw = blob if isinstance(blob, bytes) else (blob or "").encode("utf-8")
        citations = conn.execute("SELECT COUNT(*) FROM CitationTable WHERE SourceID = ?", (sid,)).fetchone()[0]
        links = conn.execute("SELECT COUNT(*) FROM CitationLinkTable l JOIN CitationTable c USING (CitationID)"
                             " WHERE c.SourceID = ?", (sid,)).fetchone()[0]
        scans = [f"{p}\\{f}" for p, f in conn.execute(
            "SELECT DISTINCT m.MediaPath, m.MediaFile FROM MediaLinkTable l JOIN MultimediaTable m USING (MediaID)"
            " JOIN CitationTable c ON l.OwnerType = ? AND l.OwnerID = c.CitationID WHERE c.SourceID = ?",
            (OWNER_CITATION, sid))]
        sources.append(Source(sid, name or "", template, templates.get(template, "free-form" if not template else "?"),
                              read_fields(blob), text or "", comments or "",
                              raw.startswith(b"\xef\xbb\xbf") or b"<?xml" in raw[:80], citations, links, scans))
    return sources


def evaluate(source: Source, everyone: list[Source]) -> None:
    flag = source.flags.append
    kind = source.kind
    if kind is None:
        flag("TYPE no source type matches the name (agree one and add a row to source_types.md)")
        parts = source.name.split(" - ")
        if len(parts) < 3:
            flag(f"G2 name has {len(parts)} part(s); expected '<Record> - <Country> - <Provider>'")
        elif parts[1].split()[0].casefold() not in COUNTRIES:
            flag(f"G2 country part {parts[1]!r} not a known country")
        if source.template not in (0, 6):
            flag(f"G1 template {source.template} ({source.template_name}) is neither 0 (free-form) nor 6"
                 " (Complex Website)")
    elif source.template != kind.template:
        flag(f"G1 template {source.template} ({source.template_name}); type '{kind.name}' has {kind.template}"
             " (the type's fields are checked once the template is right)")
        kind = None
    if source.name != source.name.strip() or "  " in source.name:
        flag("G2 name has spaces at either end or two together")

    required = {6: WEBSITE_REQUIRED, 0: FREE_FORM_REQUIRED}.get(source.template, [])
    for name in required + (kind.required if kind else []):
        if not source.fields.get(name, "").strip():
            flag(f"L2 {name} is empty")
    if source.template == 6 and source.fields.get("DatabaseCreator"):
        flag(f"L2 DatabaseCreator {source.fields['DatabaseCreator']!r} is filled")
    if kind:
        for name, values in kind.fixed.items():
            expected = [fill(v, source.capture) for v in values]
            actual = source.fields.get(name, "")
            if actual not in expected:
                flag(f"FIXED {name} {actual!r}; expected {' or '.join(repr(e) for e in expected)}")
    if source.declared:
        flag("L1 Fields saved with a byte-order mark or XML declaration")

    if kind and kind.text is not None and source.text != fill(kind.text, source.capture):
        flag(f"TEXT source text {source.text!r}; expected {fill(kind.text, source.capture)!r}")
    elif not source.text.strip():
        flag("G4 source text is empty")
    if URL_TEXT.search(source.text):
        flag("G4 source text holds a URL")
    if source.comments.strip():
        flag(f"G4 comments not empty (check for pasted website text): {source.comments[:80]!r}")

    key = " ".join(source.name.split()).casefold()
    same = [o for o in everyone if o.sid != source.sid and " ".join(o.name.split()).casefold() == key]
    if source.template == 6 and source.fields.get("DatabaseTitle"):
        db = (source.fields.get("DatabaseTitle"), source.fields.get("WebsiteTitle"))
        same += [o for o in everyone if o.sid != source.sid and o.template == 6 and o not in same
                 and (o.fields.get("DatabaseTitle"), o.fields.get("WebsiteTitle")) == db]
    if same:
        flag("G3 same name or database as " + ", ".join(f"S{o.sid} '{o.name}'" for o in same))
    if source.template == 6 and any("\\newspaper" in s.casefold() for s in source.scans):
        flag("G18 citation scans in a Newspaper folder: the newspaper may be the source")
    if not source.citations:
        flag("L3 no citations")


def report(source: Source) -> None:
    kind = source.kind.name if source.kind else "no type"
    print(f"S{source.sid}  '{source.name}'  template {source.template} ({source.template_name})  type: {kind}")
    print(f"   citations {source.citations}, links {source.links}, scans {len(source.scans)}")
    for name, value in source.fields.items():
        print(f"   field {name}: {value!r}")
    print(f"   text: {source.text!r}")
    if source.comments:
        print(f"   comments: {source.comments!r}")
    for flag in source.flags or ["(no flags)"]:
        print(f"   ! {flag}")
    print()


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="evaluate_source.py PATH_TO_RMTREE")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--source", type=int, action="append")
    which.add_argument("--all", action="store_true")
    parser.add_argument("--types", type=Path, default=TYPES_FILE)
    args = parser.parse_args(sys.argv[2:])
    types = load_types(args.types)

    conn = connect_readonly(path)
    try:
        everyone = load_sources(conn, None)
    finally:
        conn.close()
    for source in everyone:
        choose_type(source, types)
    chosen = everyone if args.all else [s for s in everyone if s.sid in set(args.source)]
    missing = sorted(set(args.source or []) - {s.sid for s in chosen})
    if missing:
        print("Sources not found: " + ", ".join(f"S{m}" for m in missing))
        return 1
    for source in chosen:
        evaluate(source, everyone)

    with output_file("evaluate_source", "sources"):
        print(f"File: {path}\nTypes: {args.types}\n")
        for source in chosen:
            report(source)
    if args.all:
        counts = Counter(flag.split()[0] for s in chosen for flag in s.flags)
        print(f"{len(chosen)} sources; {sum(1 for s in chosen if s.flags)} with flags")
        for code, n in sorted(counts.items()):
            print(f"{n:>6}  {code}")
    else:
        for source in chosen:
            kind = source.kind.name if source.kind else "no type"
            print(f"S{source.sid} '{source.name}' [{kind}]: {len(source.flags)} flags")
            for flag in source.flags:
                print(f"   ! {flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
