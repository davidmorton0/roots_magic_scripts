"""Rework FreeBMD marriage index citations: one per partner's entry, on the couple's Marriage.

For the marriage index source (default 587), following source_standards.md:
  - the source is renamed (default "Marriage Register - UK - FreeBMD"), moved to template 6
    (Complex Website) with FreeBMD as the website, and its text set;
  - citations are grouped by the couple's family: through their links to each partner's
    "Marriage Register - UK" record event (default fact type 1028) or to the family's
    Marriage event (fact type 300);
  - for each family, the transcription (FreeBMD layout: "Marriages <quarter> <year>", then
    one tab-separated line per name on the register page: surname, given names, spouse's
    surname from 1912, district, volume, page) that holds a line for each partner is used;
  - each partner gets one citation (existing ones are reused, the rest deleted): its
    transcription is the heading, the partner's own line, then "Also on the page: <Surname
    Given>; ..." for the other names; its fields are AccessDate (scan's last-modified date),
    SpecificItem "entry for <given> <surname>, <district>, vol. <v>, p. <p>[, spouse's surname
    <s>]" and Citing "General Register Office, Marriages registered in <months> <year>"; it
    is linked to the family's Marriage only, quality PIX, with only the partner's own scan
    (the one whose file name starts with the first 3 letters of the surname, then a dot and
    the initials of the given names, e.g. "BLA.H-MRB-1885-Q3.jpg");
  - the family's Marriage event is created if missing (dated as the register event);
    its date, if it is the quarter only, becomes "before" the month after the quarter;
    it gets the register event's place if it has none;
  - the partners' register events are then deleted, if nothing else is attached to them;
  - each scan gets Caption "Surname, Given – marriage index – YYYY Qn", RefNumber
    "YYYY Qn District Volume Page", Description and Date (the quarter).
Families whose citations cannot be read this way are left unchanged and listed.

Dry run by default: writes the proposed changes to
tmp/output/marriage_register/<timestamp>_freebmd_marriages.txt and changes nothing.
--apply writes them in one transaction. RootsMagic must be closed, and the file must be a
working copy.

Usage: python freebmd_marriages.py PATH_TO_RMTREE [--source ID] [--name NAME]
           [--register-fact ID] [--config FILE] [--apply]
"""

import argparse
import re
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher
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
    sort_date,
    template_fields,
    utc_mod_date,
)

DEFAULT_SOURCE, DEFAULT_REGISTER = 587, 1028
DEFAULT_NAME = "Marriage Register - UK - FreeBMD"
FACT_MARRIAGE = 300
OWNER_PERSON, OWNER_FAMILY, OWNER_EVENT, OWNER_CITATION = 0, 1, 2, 4
TEMPLATE_ID, QUALITY = 6, "PIX"
SOURCE_FIELDS = {
    "DatabaseCreator": "",
    "DatabaseTitle": "England & Wales Civil Registration Marriage Index",
    "Descriptor": "database with images",
    "WebsiteCreator": "Free UK Genealogy",
    "WebsiteTitle": "FreeBMD",
    "URL": "https://www.freebmd.org.uk",
}
SOURCE_TEXT = ("England and Wales GRO marriage index pages (printed quarterly indexes to 1983, yearly"
               " from 1984), viewed as images on the FreeBMD website")
CITATION_FIELDS = ("AccessDate", "SpecificItem", "Citing")
QUARTERS = {"Mar": (1, "January, February, and March"), "Jun": (2, "April, May, and June"),
            "Sep": (3, "July, August, and September"), "Dec": (4, "October, November, and December")}
HEAD = re.compile(r"^Marriages\s+(Mar|Jun|Sep|Dec)\s+(\d{4})", re.IGNORECASE)
ORIGIN = "Image of the General Register Office printed marriage index page, from FreeBMD."
ATTACHED = (
    "SELECT 1 FROM CitationLinkTable WHERE OwnerType = 2 AND OwnerID = ?",
    "SELECT 1 FROM MediaLinkTable WHERE OwnerType = 2 AND OwnerID = ?",
    "SELECT 1 FROM TaskLinkTable WHERE OwnerType = 2 AND OwnerID = ?",
    "SELECT 1 FROM URLTable WHERE OwnerType = 2 AND OwnerID = ?",
    "SELECT 1 FROM WitnessTable WHERE EventID = ?",
)


@dataclass
class Line:
    surname: str
    given: str
    spouse: str
    district: str
    volume: str
    page: str

    def label(self) -> str:
        return f"{self.surname} {self.given}"


@dataclass
class Partner:
    person: int
    line: Line
    scan: tuple[int, str] | None  # MediaID, full path
    citation: int = 0  # 0: a new one
    fields: dict[str, str] = field(default_factory=dict)
    text: str = ""


@dataclass
class Plan:
    family: int
    citations: list[int]
    register_events: list[int] = field(default_factory=list)
    marriage: int = 0  # 0: to be created
    quarter: tuple[int, int] = (0, 0)
    partners: list[Partner] = field(default_factory=list)
    delete: list[int] = field(default_factory=list)
    new_date: str = ""
    copy_place: tuple[int, int] = (0, 0)
    problem: str = ""


def tidy(text: str) -> str:
    text = " ".join(text.split())
    return text.title() if text.isupper() else text


def parse(text: str) -> tuple[str, int, list[Line]] | None:
    """(quarter, year, lines) from a FreeBMD marriage transcription, or None."""
    rows = [r for r in (text or "").replace("\r", "").split("\n") if r.strip()]
    rows = [r for r in rows if not r.strip().lower().startswith(("search record details", "http"))]
    if not rows:
        return None
    head = HEAD.match(rows[0].strip())
    if not head:
        return None
    lines = []
    for row in rows[1:]:
        if row.strip().lower().startswith("also on the page"):
            continue
        again = HEAD.match(row.strip())
        if again:
            if (again.group(1).title(), int(again.group(2))) != (head.group(1).title(), int(head.group(2))):
                return None
            continue
        cols = [c.strip() for c in row.split("\t")]
        if len(cols) == 5:
            cols.insert(2, "")
        if len(cols) != 6:
            return None
        lines.append(Line(*cols))
    return head.group(1).title(), int(head.group(2)), lines


def year_of(rm_date: str | None) -> int | None:
    if rm_date and len(rm_date) >= 7 and rm_date[3:7].isdigit() and rm_date[3:7] != "0000":
        return int(rm_date[3:7])
    return None


def norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


def initials(given: str) -> str:
    return "".join(w[0] for w in re.sub(r"[^A-Za-z ]", " ", given).split()).upper()


def similar(a: str, b: str) -> bool:
    """Surnames as the index and the tree spell them: equal, or close (Clitheroe/Clithero)."""
    a, b = norm(a), norm(b)
    return bool(a) and bool(b) and (a == b or SequenceMatcher(None, a, b).ratio() >= 0.8)


def name_fits(line: Line, given: str, surname: str) -> bool:
    shared = set(initials(line.given)) & set(initials(given))
    if not surname:  # a name held without a surname in the tree
        return bool(shared) and norm(line.given.split()[0]) == norm(given.split()[0]) if given else False
    return similar(line.surname, surname) and bool(shared)


def match_line(lines: list[Line], names: list[tuple[str, str]]) -> Line | None:
    found = {id(ln): ln for ln in lines for g, s in names if name_fits(ln, g, s)}
    if len(found) > 1:  # prefer the exact spelling (e.g. "Gascoigne" over "Gascoiyne")
        exact = {k: ln for k, ln in found.items() for g, s in names if s and norm(ln.surname) == norm(s)}
        found = exact or found
    return next(iter(found.values())) if len(found) == 1 else None


def match_couple(lines: list[Line], first: list[tuple[str, str]], second: list[tuple[str, str]]):
    """Lines for both partners; where the page has only these two lines and one partner's line
    is found, the other line is taken as the other partner's (an index spelling such as
    "Endres" for "Andrews")."""
    a, b = match_line(lines, first), match_line(lines, second)
    if len(lines) == 2:
        if a and not b:
            b = lines[1] if lines[0] is a else lines[0]
        elif b and not a:
            a = lines[1] if lines[0] is b else lines[0]
    return (a, b) if a and b and a is not b else (None, None)


def match_scan(scans: dict[int, str], line: Line) -> tuple[int, str] | None:
    """The scan named for this entry: first 3 letters of the surname, then the initials
    (either separator, e.g. "BLA.H-MRB-..." or "PRI-V-MRB-..."); the first initial must match.
    A name joining two people's initials with "&" (one image for both, e.g. "DIG.G&S-...")
    matches either; the second partner then gets a copy of the media row (one row per entry)."""
    want_sur, want_ini = norm(line.surname)[:3].upper(), initials(line.given)
    hits, shared = [], []
    for mid, path in scans.items():
        name = path.rsplit("\\", 1)[-1]
        joint = re.match(r"^([A-Za-z]{3})[.\-]([A-Za-z&]+)[.\-]", name)
        if joint and "&" in joint.group(2):
            if joint.group(1).upper() == want_sur and want_ini[:1] in [x[:1].upper() for x in joint.group(2).split("&")]:
                shared.append((mid, path))
            continue
        m = re.match(r"^([A-Za-z]{3})[.\-]([A-Za-z]+)[.\-]", name)
        if m and m.group(1).upper() == want_sur and m.group(2).upper()[:1] == want_ini[:1]:
            hits.append((mid, path))
    if len(hits) == 1:
        return hits[0]
    return shared[0] if not hits and len(shared) == 1 else None


def build(conn: sqlite3.Connection, source: int, register_fact: int, dates: dict[str, date]):
    names = defaultdict(list)
    for owner, given, surname in conn.execute("SELECT OwnerID, Given, Surname FROM NameTable"):
        names[owner].append((given or "", surname or ""))
        names[owner].append((surname or "", given or ""))  # names held with given and surname swapped
    texts = dict(conn.execute("SELECT CitationID, ActualText FROM CitationTable WHERE SourceID = ?", (source,)))
    scans = defaultdict(dict)
    for cid, mid, path, fname in conn.execute(
        """SELECT ml.OwnerID, m.MediaID, m.MediaPath, m.MediaFile FROM MediaLinkTable ml
           JOIN MultimediaTable m USING (MediaID) WHERE ml.OwnerType = ?
             AND ml.OwnerID IN (SELECT CitationID FROM CitationTable WHERE SourceID = ?)""",
        (OWNER_CITATION, source),
    ):
        scans[cid][mid] = f"{(path or '').rstrip(chr(92))}\\{fname or ''}"
    events = {eid: (et, ot, oid, d, pl, site) for eid, et, ot, oid, d, pl, site in conn.execute(
        "SELECT EventID, EventType, OwnerType, OwnerID, Date, PlaceID, SiteID FROM EventTable")}
    families = {fid: (fa, mo) for fid, fa, mo in conn.execute("SELECT FamilyID, FatherID, MotherID FROM FamilyTable")}
    fams_of = defaultdict(list)
    for fid, (fa, mo) in families.items():
        fams_of[fa].append(fid)
        fams_of[mo].append(fid)
    marriage_of = defaultdict(list)
    for eid, (et, ot, oid, *_ ) in events.items():
        if et == FACT_MARRIAGE and ot == OWNER_FAMILY:
            marriage_of[oid].append(eid)

    groups, register_by_family, unplaced = defaultdict(set), defaultdict(set), []
    for cid, text in texts.items():
        parsed = parse(text)
        links = conn.execute("SELECT OwnerType, OwnerID FROM CitationLinkTable WHERE CitationID = ?", (cid,)).fetchall()
        placed = False
        for ot, oid in links:
            ev = events.get(oid) if ot == OWNER_EVENT else None
            if ev and ev[0] == FACT_MARRIAGE and ev[1] == OWNER_FAMILY:
                groups[ev[2]].add(cid)
                placed = True
            elif ev and ev[0] == register_fact and ev[1] == OWNER_PERSON and parsed:
                person = ev[2]
                fits = []
                for fid in fams_of[person]:
                    spouse = families[fid][1] if families[fid][0] == person else families[fid][0]
                    if spouse and match_couple(parsed[2], names[person], names[spouse])[0]:
                        years = {year_of(events[m][3]) for m in marriage_of.get(fid, [])} - {None}
                        if not years or parsed[1] in years or parsed[1] - 1 in years:
                            fits.append(fid)
                if len(fits) > 1:  # prefer the family whose Marriage is in the transcription's year
                    dated = [f for f in fits if {year_of(events[m][3]) for m in marriage_of.get(f, [])}
                             & {parsed[1], parsed[1] - 1}]
                    fits = dated or fits
                if len(fits) == 1:
                    groups[fits[0]].add(cid)
                    register_by_family[fits[0]].add(oid)
                    placed = True
        if not placed:
            unplaced.append(cid)

    plans = []
    for fid, cids in sorted(groups.items()):
        fa, mo = families[fid]
        plan = Plan(fid, sorted(cids))
        plan.register_events = sorted(register_by_family[fid])
        plans.append(plan)
        best = None
        for cid in plan.citations:
            parsed = parse(texts[cid])
            if parsed and match_couple(parsed[2], names[fa], names[mo])[0]:
                best = parsed
                break
        if not (fa and mo):
            plan.problem = "family lacks a partner"
            continue
        if not best:
            plan.problem = "no transcription with a line for each partner"
            continue
        quarter, year, lines = best
        plan.quarter = (year, QUARTERS[quarter][0])
        for person in (fa, mo):  # the partners' register events for this marriage (same year) too
            for eid, (et, ot, oid, d, *_ ) in events.items():
                if et == register_fact and ot == OWNER_PERSON and oid == person \
                        and year_of(d) == year and eid not in plan.register_events:
                    plan.register_events.append(eid)
        all_scans = {}
        for cid in plan.citations:
            all_scans.update(scans[cid])
        same_year = {m: p for m, p in all_scans.items() if f"-{year}" in p.rsplit("\\", 1)[-1]}
        all_scans = same_year or all_scans
        couple = dict(zip((fa, mo), match_couple(lines, names[fa], names[mo])))
        for person in (fa, mo):
            line = couple[person]
            scan = match_scan(all_scans, line)
            if scan is None:
                plan.problem = f"no single scan for {line.label()} among {sorted(all_scans.values())}"
                break
            partner = Partner(person, line, scan)
            access = dates.get(scan[1].lower())
            spouse = f", spouse's surname {tidy(line.spouse)}" if line.spouse else ""
            partner.fields = {
                "AccessDate": access_date_text(access) if access else "",
                "SpecificItem": f"entry for {tidy(line.given)} {tidy(line.surname)}, {tidy(line.district)},"
                                f" vol. {line.volume}, p. {line.page}{spouse}",
                "Citing": f"General Register Office, Marriages registered in {QUARTERS[quarter][1]} {year}",
            }
            others = "; ".join(ln.label() for ln in lines if ln is not line)
            own = "\t".join([line.surname, line.given, line.spouse, line.district, line.volume, line.page])
            partner.text = f"Marriages {quarter} {year}\r\n{own}" + (f"\r\nAlso on the page: {others}" if others else "")
            plan.partners.append(partner)
        if plan.problem:
            plan.partners = []
            continue
        reuse = list(plan.citations)
        for partner in plan.partners:
            partner.citation = reuse.pop(0) if reuse else 0
        plan.delete = reuse
        marriages = marriage_of.get(fid, [])
        if len(marriages) > 1:
            plan.problem = f"family has {len(marriages)} Marriage events"
            continue
        reg_dates = [events[e][3] for e in plan.register_events if events.get(e)]
        reg_places = [(events[e][4], events[e][5]) for e in plan.register_events if events.get(e) and events[e][4]]
        y, q = plan.quarter
        first, last = q * 3 - 2, q * 3
        quarter_dates = {f"D-+{y}{first:02}00..+{y}{last:02}00..", f"DR+{y}{first:02}00..+{y}{last:02}00..",
                         f"D-+{y}{first:02}00.A+{y}{last:02}00..", f"DR+{y}{first:02}00.A+{y}{last:02}00.."}
        ny, nm = (y + 1, 1) if q == 4 else (y, last + 1)
        before = f"DB+{ny}{nm:02}00..+00000000.."
        if marriages:
            plan.marriage = marriages[0]
            current = events[plan.marriage][3] or "."
            if current in quarter_dates or current == ".":
                plan.new_date = before
            if not events[plan.marriage][4] and reg_places:
                plan.copy_place = reg_places[0]
        else:
            plan.new_date = before
            plan.copy_place = reg_places[0] if reg_places else (0, 0)
    return plans, unplaced


def media_values(partner: Partner, quarter: tuple[int, int]) -> dict:
    y, q = quarter
    ln = partner.line
    date_text = f"D-+{y}{q * 3 - 2:02}00..+{y}{q * 3:02}00.."
    citing = partner.fields["Citing"].removeprefix("General Register Office, ")
    return {
        "Caption": f"{tidy(ln.surname)}, {tidy(ln.given)} – marriage index – {y} Q{q}",
        "RefNumber": f"{y} Q{q} {tidy(ln.district)} {ln.volume} {ln.page}",
        "Description": f"{citing}: {partner.fields['SpecificItem'].removeprefix('entry for ')}. {ORIGIN}",
        "Date": date_text,
        "SortDate": sort_date(date_text),
    }


def write_report(plans, unplaced, names) -> None:
    ok = [p for p in plans if not p.problem]
    bad = [p for p in plans if p.problem]
    print(f"Families: {len(plans)}; to rework {len(ok)}; left unchanged {len(bad)};"
          f" citations not linked to a family {len(unplaced)}")
    if bad:
        print("\n== Left unchanged")
        for p in bad:
            fa_mo = ", ".join(str(c) for c in p.citations)
            print(f"   F{p.family}: {p.problem} (citations {fa_mo})")
    if unplaced:
        print("\n== Citations not linked to a family: " + ", ".join(f"C{c}" for c in unplaced))
    print("\n== Proposed changes")
    for p in ok:
        print(f"\nF{p.family} Marriage {'E' + str(p.marriage) if p.marriage else '(new)'}"
              f"{' date -> ' + p.new_date if p.new_date else ''}{' place from register' if p.copy_place[0] else ''}")
        for pt in p.partners:
            print(f"   {'C' + str(pt.citation) if pt.citation else 'new citation'} {names.get(pt.person)} [P{pt.person}]"
                  f" scan M{pt.scan[0]} {pt.scan[1].rsplit(chr(92), 1)[-1]}")
            print(f"      SpecificItem: {pt.fields['SpecificItem']}")
            print(f"      AccessDate: {pt.fields['AccessDate']}; text: {pt.text!r}")
        if p.delete:
            print("   delete " + ", ".join(f"C{c}" for c in p.delete))
        print("   register events removed: " + ", ".join(f"E{e}" for e in p.register_events))


def attached(conn: sqlite3.Connection, eid: int) -> bool:
    """True if anything is still attached to the event (citations, media, tasks, web links, witnesses)."""
    return any(conn.execute(sql, (eid,)).fetchone() for sql in ATTACHED)


def apply(path: Path, source: int, name: str, plans: list[Plan]) -> tuple[int, int]:
    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    done = deleted_events = 0
    try:
        conn.execute("UPDATE SourceTable SET Name = ?, TemplateID = ?, Fields = ?, ActualText = ?, Comments = '',"
                     " UTCModDate = ? WHERE SourceID = ?",
                     (name, TEMPLATE_ID, fields_blob(SOURCE_FIELDS, declaration=False), SOURCE_TEXT, stamp, source))
        for p in plans:
            if p.problem:
                continue
            if not p.marriage:
                p.marriage = conn.execute(
                    "INSERT INTO EventTable (EventType, OwnerType, OwnerID, FamilyID, PlaceID, SiteID, Date, SortDate,"
                    " IsPrimary, IsPrivate, Proof, Status, Sentence, Details, Note, UTCModDate)"
                    " VALUES (?, ?, ?, 0, ?, ?, ?, ?, 1, 0, 0, 0, '', '', '', ?)",
                    (FACT_MARRIAGE, OWNER_FAMILY, p.family, p.copy_place[0], p.copy_place[1], p.new_date,
                     sort_date(p.new_date), stamp)).lastrowid
            else:
                if p.new_date:
                    conn.execute("UPDATE EventTable SET Date = ?, SortDate = ?, UTCModDate = ? WHERE EventID = ?",
                                 (p.new_date, sort_date(p.new_date), stamp, p.marriage))
                if p.copy_place[0]:
                    conn.execute("UPDATE EventTable SET PlaceID = ?, SiteID = ?, UTCModDate = ? WHERE EventID = ?",
                                 (*p.copy_place, stamp, p.marriage))
            for cid in p.delete:
                conn.execute("DELETE FROM CitationLinkTable WHERE CitationID = ?", (cid,))
                conn.execute("DELETE FROM MediaLinkTable WHERE OwnerType = ? AND OwnerID = ?", (OWNER_CITATION, cid))
                conn.execute("DELETE FROM CitationTable WHERE CitationID = ?", (cid,))
            used = set()
            for pt in p.partners:
                if pt.scan[0] in used:  # one image for both: a copy of the media row for this entry
                    copy = conn.execute(
                        "INSERT INTO MultimediaTable (MediaType, MediaPath, MediaFile, URL, Thumbnail, Caption,"
                        " RefNumber, Date, SortDate, Description, UTCModDate) SELECT MediaType, MediaPath,"
                        " MediaFile, URL, Thumbnail, '', '', '.', 0, '', ? FROM MultimediaTable WHERE MediaID = ?",
                        (stamp, pt.scan[0])).lastrowid
                    pt.scan = (copy, pt.scan[1])
                used.add(pt.scan[0])
                cname = "; ".join(pt.fields[f] for f in CITATION_FIELDS)
                blob = fields_blob(pt.fields, declaration=False)
                if pt.citation:
                    conn.execute("UPDATE CitationTable SET Fields = ?, CitationName = ?, ActualText = ?, UTCModDate = ?"
                                 " WHERE CitationID = ?", (blob, cname, pt.text, stamp, pt.citation))
                    conn.execute("DELETE FROM CitationLinkTable WHERE CitationID = ?", (pt.citation,))
                    conn.execute("DELETE FROM MediaLinkTable WHERE OwnerType = ? AND OwnerID = ? AND MediaID <> ?",
                                 (OWNER_CITATION, pt.citation, pt.scan[0]))
                else:
                    pt.citation = conn.execute(
                        "INSERT INTO CitationTable (SourceID, Comments, ActualText, RefNumber, Footnote, ShortFootnote,"
                        " Bibliography, Fields, UTCModDate, CitationName) VALUES (?, '', ?, '', '', '', '', ?, ?, ?)",
                        (source, pt.text, blob, stamp, cname)).lastrowid
                if not conn.execute("SELECT 1 FROM MediaLinkTable WHERE OwnerType = ? AND OwnerID = ? AND MediaID = ?",
                                    (OWNER_CITATION, pt.citation, pt.scan[0])).fetchone():
                    conn.execute("INSERT INTO MediaLinkTable (MediaID, OwnerType, OwnerID, IsPrimary, Include1, Include2,"
                                 " Include3, Include4, SortOrder, RectLeft, RectTop, RectRight, RectBottom, Comments,"
                                 " UTCModDate) VALUES (?, ?, ?, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, '', ?)",
                                 (pt.scan[0], OWNER_CITATION, pt.citation, stamp))
                conn.execute("INSERT INTO CitationLinkTable (CitationID, OwnerType, OwnerID, SortOrder, Quality,"
                             " IsPrivate, Flags, UTCModDate) VALUES (?, ?, ?, 0, ?, 0, 0, ?)",
                             (pt.citation, OWNER_EVENT, p.marriage, QUALITY, stamp))
                values = media_values(pt, p.quarter)
                conn.execute("UPDATE MultimediaTable SET Caption = ?, RefNumber = ?, Description = ?, Date = ?,"
                             " SortDate = ?, UTCModDate = ? WHERE MediaID = ?", (*values.values(), stamp, pt.scan[0]))
            for eid in p.register_events:
                if attached(conn, eid):
                    continue
                conn.execute("DELETE FROM EventTable WHERE EventID = ?", (eid,))
                deleted_events += 1
            done += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return done, deleted_events


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="freebmd_marriages.py PATH_TO_RMTREE")
    parser.add_argument("--source", type=int, default=DEFAULT_SOURCE)
    parser.add_argument("--name", default=DEFAULT_NAME)
    parser.add_argument("--register-fact", type=int, default=DEFAULT_REGISTER)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(sys.argv[2:])

    conn = connect_readonly(path)
    try:
        if conn.execute("SELECT 1 FROM SourceTable WHERE SourceID = ?", (args.source,)).fetchone() is None:
            print(f"Source S{args.source} not found")
            return 1
        expected = list(SOURCE_FIELDS) + list(CITATION_FIELDS)
        if sorted(n for n, _ in template_fields(conn, TEMPLATE_ID)) != sorted(expected):
            print(f"Template {TEMPLATE_ID} does not have the expected fields: {expected}")
            return 1
        dates = list_windows_file_dates(load_config(args.config)["scan_root"])
        plans, unplaced = build(conn, args.source, args.register_fact, dates)
        names = person_names(conn)
    finally:
        conn.close()
    bad = sum(1 for p in plans if p.problem)
    with output_file("freebmd_marriages", "marriage_register"):
        write_report(plans, unplaced, names)
    print(f"{len(plans)} families; {len(plans) - bad} to rework; {bad} left unchanged;"
          f" {len(unplaced)} citations not linked to a family")
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0
    done, deleted = apply(path, args.source, args.name, plans)
    print(f"Applied: source S{args.source}; {done} families reworked; {deleted} register events deleted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
