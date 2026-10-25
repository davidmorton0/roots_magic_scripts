"""Check a RootsMagic .rmtree database for common issues.

Opens the file read-only. Runs every check, writes each record with an issue
to tmp/output/general/<timestamp>_check.txt, and prints a summary of counts.

Scan checks compare the database with the files under scan_root (see
config.example.toml). The file list comes from Windows PowerShell unless
--scan-list gives a file with one full Windows path per line.

Codes used were found from existing links in the database, not documentation:
  MediaLinkTable.OwnerType     0 person, 2 event, 3 source, 4 citation
  CitationLinkTable.OwnerType  0 person, 1 family, 2 event
  EventTable.OwnerType         0 person, 1 family
  MultimediaTable.MediaType    1 image, 2 file
  PlaceTable.PlaceType         0 place, 1 RootsMagic's temple list (not checked), 2 place detail
Only the year of an event date is read (from "D?+YYYYMMDD..."), apart from
showing simple exact dates as YYYY-MM-DD.

Usage: python check.py PATH_TO_RMTREE [--config FILE] [--scan-list FILE] [--no-scans]
"""

import argparse
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path, PureWindowsPath

from rmutils import (
    connect_readonly,
    db_path_arg,
    list_windows_files,
    load_config,
    output_file,
    person_names,
)

OWNER_PERSON, OWNER_FAMILY, OWNER_EVENT, OWNER_SOURCE, OWNER_CITATION = 0, 1, 2, 3, 4
MEDIA_IMAGE, MEDIA_FILE = 1, 2
PLACE_TEMPLE, PLACE_DETAIL = 1, 2  # type 1: RootsMagic's own list of LDS temples ("AUCKL - Auckland ...")
FACT_BIRTH, FACT_DEATH, FACT_CHRISTEN = 1, 2, 3
FIRST_CUSTOM_FACT = 1000
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".tif", ".tiff", ".png", ".gif", ".webp", ".bmp"}
YEAR_IN_NAME = re.compile(r"\b(1[5-9]\d\d|20\d\d)\b")
MIN_EVENTS_FOR_STYLE = 5

CHECKS = []


def check(code: str, title: str, needs_scans: bool = False):
    def register(fn):
        CHECKS.append((code, title, needs_scans, fn))
        return fn

    return register


def year_of(date: str | None) -> int | None:
    if date and len(date) >= 11 and date[0] == "D" and date[2] == "+":
        digits = date[3:7]
        if digits.isdigit() and digits != "0000":
            return int(digits)
    return None


def date_text(date: str | None) -> str:
    if not date or date == ".":
        return "(no date)"
    if (
        date.startswith("D.+")
        and date[11:] == "..+00000000.."
        and date[3:11].isdigit()
        and date[3:7] != "0000"
    ):
        parts = [date[3:7]]
        if date[7:9] != "00":
            parts.append(date[7:9])
            if date[9:11] != "00":
                parts.append(date[9:11])
        return "-".join(parts)
    return date


def media_path(path: str, file: str) -> str:
    return f"{(path or '').rstrip(chr(92))}\\{file or ''}"


class Tree:
    """Everything the checks need, loaded once."""

    def __init__(self, conn: sqlite3.Connection, cfg: dict, disk: list[str] | None):
        self.cfg = cfg
        self.disk = disk
        self.root = cfg["scan_root"].rstrip("\\").lower() + "\\"
        self.names = person_names(conn)
        self.sex = dict(conn.execute("SELECT PersonID, Sex FROM PersonTable"))
        self.facts = {
            fid: (name, use_date, use_place)
            for fid, name, use_date, use_place in conn.execute(
                "SELECT FactTypeID, Name, UseDate, UsePlace FROM FactTypeTable"
            )
        }
        self.families = {
            fid: (father, mother)
            for fid, father, mother in conn.execute(
                "SELECT FamilyID, FatherID, MotherID FROM FamilyTable"
            )
        }
        self.children = conn.execute(
            "SELECT ChildID, FamilyID FROM ChildTable"
        ).fetchall()
        self.events = conn.execute(
            "SELECT EventID, EventType, OwnerType, OwnerID, PlaceID, Date, IsPrimary"
            " FROM EventTable ORDER BY EventID"
        ).fetchall()
        self.events_by_id = {row[0]: row for row in self.events}
        self.sources = dict(conn.execute("SELECT SourceID, Name FROM SourceTable"))
        self.citations = {
            cid: (sid, name)
            for cid, sid, name in conn.execute(
                "SELECT CitationID, SourceID, CitationName FROM CitationTable"
            )
        }
        self.citation_links = defaultdict(list)
        for cid, otype, oid in conn.execute(
            "SELECT CitationID, OwnerType, OwnerID FROM CitationLinkTable"
        ):
            self.citation_links[cid].append((otype, oid))
        self.media = conn.execute(
            "SELECT MediaID, MediaType, MediaPath, MediaFile FROM MultimediaTable"
            " ORDER BY MediaID"
        ).fetchall()
        self.media_links = defaultdict(list)
        self.media_link_rows = conn.execute(
            "SELECT LinkID, MediaID, OwnerType, OwnerID FROM MediaLinkTable"
        ).fetchall()
        for _, mid, otype, oid in self.media_link_rows:
            self.media_links[mid].append((otype, oid))

        self.places = conn.execute(
            "SELECT PlaceID, PlaceType, Name, MasterID FROM PlaceTable ORDER BY PlaceID"
        ).fetchall()
        self.used_places = Counter()
        for table in ("EventTable", "FANTable"):
            for place, site in conn.execute(f"SELECT PlaceID, SiteID FROM {table}"):
                self.used_places[place] += 1
                self.used_places[site] += 1
        for _, _, _, master in self.places:
            self.used_places[master] += 1

        self.cited_events = {
            oid
            for links in self.citation_links.values()
            for otype, oid in links
            if otype == OWNER_EVENT
        }
        self.births = self._life_years(FACT_BIRTH)
        self.deaths = self._life_years(FACT_DEATH)

    def _life_years(self, fact: int) -> dict[int, int]:
        years = {}
        for _, etype, otype, oid, _, date, primary in self.events:
            year = year_of(date)
            if otype == OWNER_PERSON and etype == fact and year:
                if oid not in years or primary:
                    years[oid] = year
        return years

    def fact_name(self, fact: int) -> str:
        return self.facts.get(fact, (f"fact {fact}",))[0]

    def person(self, pid: int) -> str:
        return f"{self.names.get(pid, '(missing person)')} [P{pid}]"

    def family(self, fid: int) -> str:
        father, mother = self.families.get(fid, (0, 0))
        names = [self.names.get(p, "?") if p else "?" for p in (father, mother)]
        return f"{names[0]} & {names[1]} [F{fid}]"

    def owner(self, otype: int, oid: int) -> str:
        if otype == OWNER_PERSON:
            return self.person(oid)
        if otype == OWNER_FAMILY:
            return self.family(oid)
        return f"owner type {otype} id {oid}"

    def event(self, row) -> str:
        eid, etype, otype, oid, _, date, _ = row
        return f"{self.fact_name(etype)} {date_text(date)} - {self.owner(otype, oid)} [E{eid}]"

    def event_id(self, eid: int) -> str:
        row = self.events_by_id.get(eid)
        return self.event(row) if row else f"(missing event) [E{eid}]"

    def citation(self, cid: int) -> str:
        sid, name = self.citations.get(cid, (0, ""))
        source = self.sources.get(sid, "(missing source)")
        return f"{source}: {name or '(no name)'} [C{cid}]"

    def citation_owner(self, otype: int, oid: int) -> str:
        if otype == OWNER_EVENT:
            return self.event_id(oid)
        return self.owner(otype, oid)

    def under_root(self, path: str) -> bool:
        return path.lower().startswith(self.root)

    def is_scan(self, path: str) -> bool:
        if not self.under_root(path):
            return False
        parts = PureWindowsPath(path[len(self.root) :]).parts
        if len(parts) < 2:
            return False
        not_scans = {f.lower() for f in self.cfg["not_scan_folders"]}
        skip = {f.lower() for f in self.cfg["skip_subfolders"]}
        if parts[0].lower() in not_scans:
            return False
        if any(p.lower() in skip for p in parts[:-1]):
            return False
        exts = {e.lower() for e in self.cfg["scan_extensions"]}
        return PureWindowsPath(path).suffix.lower() in exts

    def person_events(self):
        for row in self.events:
            if row[2] == OWNER_PERSON:
                yield row


# --- Scans and media -------------------------------------------------------


@check("scan_not_in_db", "Scan files on disk not in the database", needs_scans=True)
def scan_not_in_db(t: Tree) -> list[str]:
    known = {media_path(p, f).lower() for _, _, p, f in t.media}
    return sorted(d for d in t.disk if t.is_scan(d) and d.lower() not in known)


@check("media_file_missing", "Media rows whose file is not on disk", needs_scans=True)
def media_file_missing(t: Tree) -> list[str]:
    on_disk = {d.lower() for d in t.disk}
    out = []
    for mid, _, path, file in t.media:
        full = media_path(path, file)
        if t.under_root(full) and full.lower() not in on_disk:
            out.append(f"{full} [M{mid}]")
    return out


@check("media_outside_root", "Media rows whose path is not under the scan folder")
def media_outside_root(t: Tree) -> list[str]:
    return [
        f"{media_path(path, file)} [M{mid}]"
        for mid, _, path, file in t.media
        if not t.under_root(media_path(path, file))
    ]


@check("media_unlinked", "Media not attached to anything")
def media_unlinked(t: Tree) -> list[str]:
    return [
        f"{media_path(path, file)} [M{mid}]"
        for mid, _, path, file in t.media
        if not t.media_links.get(mid)
    ]


@check("media_not_on_citation", "Media attached to an event or source but no citation")
def media_not_on_citation(t: Tree) -> list[str]:
    out = []
    for mid, _, path, file in t.media:
        links = t.media_links.get(mid, [])
        if any(otype == OWNER_CITATION for otype, _ in links):
            continue
        owners = []
        for otype, oid in links:
            if otype == OWNER_EVENT:
                owners.append(t.event_id(oid))
            elif otype == OWNER_SOURCE:
                owners.append(f"source {t.sources.get(oid, '?')} [S{oid}]")
        if owners:
            out.append(f"{media_path(path, file)} [M{mid}] -> {'; '.join(owners)}")
    return out


@check("media_type_mismatch", "PDF stored as Image, or image stored as File")
def media_type_mismatch(t: Tree) -> list[str]:
    out = []
    for mid, mtype, path, file in t.media:
        ext = PureWindowsPath(file or "").suffix.lower()
        if mtype == MEDIA_IMAGE and ext == ".pdf":
            out.append(f"{media_path(path, file)} [M{mid}] is Image")
        elif mtype == MEDIA_FILE and ext in IMAGE_EXTENSIONS:
            out.append(f"{media_path(path, file)} [M{mid}] is File")
    return out


@check("media_duplicate", "Same file in more than one media row")
def media_duplicate(t: Tree) -> list[str]:
    groups = defaultdict(list)
    for mid, _, path, file in t.media:
        groups[media_path(path, file).lower()].append((mid, media_path(path, file)))
    return [
        f"{rows[0][1]} [{', '.join(f'M{mid}' for mid, _ in rows)}]"
        for rows in groups.values()
        if len(rows) > 1
    ]


@check("media_link_orphan", "Media links pointing to a missing record")
def media_link_orphan(t: Tree) -> list[str]:
    exists = {
        OWNER_PERSON: t.names,
        OWNER_EVENT: t.events_by_id,
        OWNER_SOURCE: t.sources,
        OWNER_CITATION: t.citations,
    }
    media_ids = {row[0] for row in t.media}
    out = []
    for link_id, mid, otype, oid in t.media_link_rows:
        if mid not in media_ids:
            out.append(f"link {link_id}: media M{mid} missing")
        elif otype in exists and oid not in exists[otype]:
            out.append(f"link {link_id}: M{mid} -> owner type {otype} id {oid} missing")
    return out


# --- Sources and citations -------------------------------------------------


@check("citation_no_media", "Citations with no scan attached")
def citation_no_media(t: Tree) -> list[str]:
    with_media = {
        oid
        for links in t.media_links.values()
        for otype, oid in links
        if otype == OWNER_CITATION
    }
    out = []
    for cid in sorted(t.citations):
        if cid not in with_media:
            links = t.citation_links.get(cid, [])
            used = t.citation_owner(*links[0]) if links else "(not used)"
            more = f" (+{len(links) - 1} more)" if len(links) > 1 else ""
            out.append(f"{t.citation(cid)} - {used}{more}")
    return out


@check("citation_unused", "Citations not attached to anything")
def citation_unused(t: Tree) -> list[str]:
    return [t.citation(cid) for cid in sorted(t.citations) if not t.citation_links.get(cid)]


@check("citation_link_orphan", "Citation links pointing to a missing record")
def citation_link_orphan(t: Tree) -> list[str]:
    exists = {OWNER_PERSON: t.names, OWNER_FAMILY: t.families, OWNER_EVENT: t.events_by_id}
    out = []
    for cid, links in sorted(t.citation_links.items()):
        for otype, oid in links:
            if cid not in t.citations:
                out.append(f"citation C{cid} missing (owner type {otype} id {oid})")
            elif otype in exists and oid not in exists[otype]:
                out.append(f"{t.citation(cid)} -> owner type {otype} id {oid} missing")
    return out


@check("source_unused", "Sources with no citations")
def source_unused(t: Tree) -> list[str]:
    used = {sid for sid, _ in t.citations.values()}
    return [f"{name} [S{sid}]" for sid, name in sorted(t.sources.items()) if sid not in used]


# --- Events ----------------------------------------------------------------


@check("record_event_no_citation", "Record events (custom facts) with no citation")
def record_event_no_citation(t: Tree) -> list[str]:
    return [
        t.event(row)
        for row in t.events
        if row[1] >= FIRST_CUSTOM_FACT and row[0] not in t.cited_events
    ]


@check("event_no_citation", "Standard events (birth, death, marriage...) with no citation")
def event_no_citation(t: Tree) -> list[str]:
    return [
        t.event(row)
        for row in t.events
        if row[1] < FIRST_CUSTOM_FACT and row[0] not in t.cited_events
    ]


@check("event_no_date", "Events with no date (where the fact type uses a date)")
def event_no_date(t: Tree) -> list[str]:
    return [
        t.event(row)
        for row in t.events
        if row[5] in (None, "", ".") and t.facts.get(row[1], ("", 1, 1))[1]
    ]


@check("event_no_place", "Events with no place (where the fact type uses a place)")
def event_no_place(t: Tree) -> list[str]:
    return [
        t.event(row)
        for row in t.events
        if not row[4] and t.facts.get(row[1], ("", 1, 1))[2]
    ]


@check("fact_year_mismatch", "Event year differs from the year in the fact name")
def fact_year_mismatch(t: Tree) -> list[str]:
    out = []
    for row in t.events:
        match = YEAR_IN_NAME.search(t.fact_name(row[1]))
        year = year_of(row[5])
        if match and year and year != int(match.group(1)):
            out.append(t.event(row))
    return out


@check("date_style_unusual", "Record events dated in a different style from most of their type")
def date_style_unusual(t: Tree) -> list[str]:
    def style(date):
        return date[:2] + date[12:13]

    by_fact = defaultdict(list)
    for row in t.events:
        if row[1] >= FIRST_CUSTOM_FACT and year_of(row[5]):
            by_fact[row[1]].append(row)
    out = []
    for fact, rows in sorted(by_fact.items()):
        if len(rows) < MIN_EVENTS_FOR_STYLE:
            continue
        counts = Counter(style(r[5]) for r in rows)
        common = counts.most_common(1)[0][0]
        example = next(r[5] for r in rows if style(r[5]) == common)
        for row in rows:
            if style(row[5]) != common:
                out.append(f"{t.event(row)} - most look like {example}")
    return out


@check("event_before_birth", "Person events dated before their birth year")
def event_before_birth(t: Tree) -> list[str]:
    out = []
    for row in t.person_events():
        born, year = t.births.get(row[3]), year_of(row[5])
        if row[1] != FACT_BIRTH and born and year and year < born:
            out.append(f"{t.event(row)} - born {born}")
    return out


@check("event_after_death", "Person events dated after their death year")
def event_after_death(t: Tree) -> list[str]:
    allowed = {name.lower() for name in t.cfg["after_death_facts"]}
    out = []
    for row in t.person_events():
        died, year = t.deaths.get(row[3]), year_of(row[5])
        name = t.fact_name(row[1]).lower()
        if row[1] != FACT_DEATH and name not in allowed and died and year and year > died:
            out.append(f"{t.event(row)} - died {died}")
    return out


# --- People ----------------------------------------------------------------


# --- Places ------------------------------------------------------------------


def place_key(name: str) -> list[str]:
    """Words of a place name, ignoring case, punctuation, "the" and a final s or 's."""
    words = re.sub(r"[^\w\s]", " ", name.casefold().replace("'s", "")).split()
    return [w.removesuffix("s") if len(w) > 3 else w for w in words if w != "the"]


@check("place_unused", "Places and place details used by no fact, FAN row or place detail")
def place_unused(t: Tree) -> list[str]:
    return [
        f"{name} [L{pid}]" + (" (detail)" if ptype == PLACE_DETAIL else "")
        for pid, ptype, name, _ in t.places
        if ptype != PLACE_TEMPLE and not t.used_places.get(pid)
    ]


@check("place_detail_similar", "Place details under one place with near-identical names")
def place_detail_similar(t: Tree) -> list[str]:
    by_master = defaultdict(list)
    for pid, ptype, name, master in t.places:
        if ptype == PLACE_DETAIL:
            by_master[master].append((pid, name, place_key(name)))
    masters = {pid: name for pid, _, name, _ in t.places}
    out = []
    for master, details in sorted(by_master.items()):
        for i, (pid1, name1, key1) in enumerate(details):
            for pid2, name2, key2 in details[i + 1:]:
                shorter, longer = sorted((key1, key2), key=len)
                if shorter and longer[: len(shorter)] == shorter:
                    out.append(f"{name1} [L{pid1}] / {name2} [L{pid2}] - under {masters.get(master, '?')} [L{master}]")
    return out


@check("person_no_name", "People with no primary name")
def person_no_name(t: Tree) -> list[str]:
    return [t.person(pid) for pid, name in sorted(t.names.items()) if name == "(no primary name)"]


@check("person_sex_code", "People whose sex code is not 0 or 1")
def person_sex_code(t: Tree) -> list[str]:
    return [f"{t.person(pid)} code {sex}" for pid, sex in sorted(t.sex.items()) if sex not in (0, 1)]


@check("person_no_events", "People with no events at all")
def person_no_events(t: Tree) -> list[str]:
    owners = {row[3] for row in t.person_events()}
    return [t.person(pid) for pid in sorted(t.names) if pid not in owners]


@check("person_no_birth", "People with no birth or christening event")
def person_no_birth(t: Tree) -> list[str]:
    owners = {row[3] for row in t.person_events() if row[1] in (FACT_BIRTH, FACT_CHRISTEN)}
    return [t.person(pid) for pid in sorted(t.names) if pid not in owners]


@check("person_unconnected", "People with no parents, partner or children")
def person_unconnected(t: Tree) -> list[str]:
    linked = {child for child, _ in t.children}
    linked |= {p for pair in t.families.values() for p in pair if p}
    return [t.person(pid) for pid in sorted(t.names) if pid not in linked]


@check("person_multiple_primary", "More than one primary birth or death event")
def person_multiple_primary(t: Tree) -> list[str]:
    counts = Counter(
        (row[3], row[1])
        for row in t.person_events()
        if row[1] in (FACT_BIRTH, FACT_DEATH) and row[6]
    )
    return [
        f"{t.person(pid)} has {n} primary {t.fact_name(fact)} events"
        for (pid, fact), n in sorted(counts.items())
        if n > 1
    ]


@check("birth_after_death", "Birth year after death year")
def birth_after_death(t: Tree) -> list[str]:
    return [
        f"{t.person(pid)} born {born}, died {t.deaths[pid]}"
        for pid, born in sorted(t.births.items())
        if pid in t.deaths and born > t.deaths[pid]
    ]


# --- Families --------------------------------------------------------------


@check("family_one_partner", "Families with only one partner recorded")
def family_one_partner(t: Tree) -> list[str]:
    return [
        t.family(fid)
        for fid, (father, mother) in sorted(t.families.items())
        if not father or not mother
    ]


@check("parent_age", "Parent too young, too old, or dead at a child's birth")
def parent_age(t: Tree) -> list[str]:
    min_age, max_mother = t.cfg["min_parent_age"], t.cfg["max_mother_age"]
    out = []
    for child, fid in t.children:
        born = t.births.get(child)
        if not born:
            continue
        father, mother = t.families.get(fid, (0, 0))
        for parent, role in ((father, "father"), (mother, "mother")):
            problems = []
            parent_born, parent_died = t.births.get(parent), t.deaths.get(parent)
            if parent_born:
                age = born - parent_born
                if age < min_age:
                    problems.append(f"{role} aged {age}")
                if role == "mother" and age > max_mother:
                    problems.append(f"mother aged {age}")
            if parent_died:
                limit = parent_died + (1 if role == "father" else 0)
                if born > limit:
                    problems.append(f"{role} died {parent_died}")
            if parent and problems:
                out.append(
                    f"{t.person(child)} born {born} - {t.person(parent)}: {', '.join(problems)}"
                )
    return out


@check("family_event_age", "Family events (e.g. marriage) with a partner under age or dead")
def family_event_age(t: Tree) -> list[str]:
    min_age = t.cfg["min_marriage_age"]
    out = []
    for row in t.events:
        year = year_of(row[5])
        if row[2] != OWNER_FAMILY or not year:
            continue
        problems = []
        for partner in t.families.get(row[3], (0, 0)):
            born, died = t.births.get(partner), t.deaths.get(partner)
            if born and year - born < min_age:
                problems.append(f"{t.person(partner)} aged {year - born}")
            if died and year > died:
                problems.append(f"{t.person(partner)} died {died}")
        if problems:
            out.append(f"{t.event(row)} - {', '.join(problems)}")
    return out


# --- Main ------------------------------------------------------------------


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="check.py PATH_TO_RMTREE")
    parser.add_argument("--config", type=Path, help="settings file (default config.toml)")
    parser.add_argument("--scan-list", type=Path, help="file listing scan paths")
    parser.add_argument("--no-scans", action="store_true", help="skip disk checks")
    return parser.parse_args(argv)


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    args = parse_args(sys.argv[2:])
    cfg = load_config(args.config)

    if args.no_scans:
        disk = None
    elif args.scan_list:
        lines = args.scan_list.read_text(encoding="utf-8").splitlines()
        disk = [line.strip().lstrip("﻿") for line in lines if line.strip()]
    else:
        disk = list_windows_files(cfg["scan_root"])

    conn = connect_readonly(path)
    try:
        tree = Tree(conn, cfg, disk)
    finally:
        conn.close()

    results = [
        (code, title, None if needs_scans and disk is None else fn(tree))
        for code, title, needs_scans, fn in CHECKS
    ]
    summary = [
        f"{'skipped' if lines is None else len(lines):>7}  {code:<26} {title}"
        for code, title, lines in results
    ]

    with output_file("check"):
        print(f"File: {path}")
        print(f"Scan files listed: {'skipped' if disk is None else len(disk)}\n")
        print("\n".join(summary))
        for code, title, lines in results:
            if lines:
                print(f"\n== {code}: {title} ({len(lines)})")
                for line in lines:
                    print(f"   {line}")
    print("\n".join(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
