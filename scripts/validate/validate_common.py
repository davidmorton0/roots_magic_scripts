"""Shared code for the per-record-type validation scripts (scripts/validate/validate_*.py).

Each script registers its checks with a Checks list and calls run(). The tree is opened read-only
and loaded once into a Tree; the connection stays open while the checks run, for checks that query
it directly. Each check returns one line per record with an issue.

Codes used were found from existing links in the database, not documentation:
  MediaLinkTable.OwnerType     0 person, 2 event, 3 source, 4 citation
  CitationLinkTable.OwnerType  0 person, 1 family, 2 event, 7 name
  EventTable.OwnerType         0 person, 1 family
  MultimediaTable.MediaType    1 image, 2 file
  PlaceTable.PlaceType         0 place, 1 RootsMagic's temple list (not checked), 2 place detail
"""

import argparse
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path, PureWindowsPath

from rmutils import (
    connect_readonly,
    event_sort_date,
    list_windows_files,
    load_config,
    output_file,
    person_names,
)

OWNER_PERSON, OWNER_FAMILY, OWNER_EVENT, OWNER_SOURCE, OWNER_CITATION, OWNER_NAME = 0, 1, 2, 3, 4, 7
MEDIA_IMAGE, MEDIA_FILE = 1, 2
PLACE, PLACE_TEMPLE, PLACE_DETAIL = 0, 1, 2
FACT_BIRTH, FACT_DEATH, FACT_CHRISTEN = 1, 2, 3
FIRST_CUSTOM_FACT = 1000
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".tif", ".tiff", ".png", ".gif", ".webp", ".bmp"}

# RootsMagic's encoded date, as found in the tree (2026-10-28): D, a kind (. single, - range,
# R between, B before, A after, S unconfirmed), +YYYYMMDD, two flag characters ("." or "/" for a
# double-dated year, then "." or "A" for about), +YYYYMMDD (00000000 for a single date), "..".
DATE_FORM = re.compile(r"D[.\-RBAS]\+(\d{8})[./][.A]\+(\d{8})\.\.")
NO_DATE = "."


def year_of(date: str | None) -> int | None:
    if date and len(date) >= 11 and date[0] == "D" and date[2] == "+":
        digits = date[3:7]
        if digits.isdigit() and digits != "0000":
            return int(digits)
    return None


def date_text(date: str | None) -> str:
    if not date or date == NO_DATE:
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


def date_problem(date: str | None) -> str | None:
    """Why a date string is not a well-formed encoded date, or None if it is (or is "." for none)."""
    if date == NO_DATE:
        return None
    if not date:
        return "empty (no date is \".\")"
    if date.startswith("T"):
        return "text date, not an encoded date"
    match = DATE_FORM.fullmatch(date)
    if not match:
        return "form not known"
    for part in match.groups():
        month, day = int(part[4:6]), int(part[6:8])
        if month > 12 or day > 31 or (month == 0 and day):
            return f"month or day out of range in {part}"
    return None


def sort_date_problem(date: str | None, sort: int | None) -> str | None:
    """SortDate differs from what rmutils works out for the date (None where it cannot work it out)."""
    expected = event_sort_date(date) if date else None
    if expected is not None and sort != expected:
        return f"SortDate {sort}, expected {expected}"
    return None


def media_path(path: str, file: str) -> str:
    return f"{(path or '').rstrip(chr(92))}\\{file or ''}"


def full_name(given, surname) -> str:
    return " ".join(p for p in (given, surname) if p) or "(blank)"


class Tree:
    """Everything the checks need, loaded once; conn stays open for checks that query it."""

    def __init__(self, conn: sqlite3.Connection, cfg: dict, disk: list[str] | None):
        self.conn = conn
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
            for fid, father, mother in conn.execute("SELECT FamilyID, FatherID, MotherID FROM FamilyTable")
        }
        self.children = conn.execute("SELECT ChildID, FamilyID FROM ChildTable").fetchall()
        self.events = conn.execute(
            "SELECT EventID, EventType, OwnerType, OwnerID, PlaceID, Date, IsPrimary FROM EventTable ORDER BY EventID"
        ).fetchall()
        self.events_by_id = {row[0]: row for row in self.events}
        self.sources = dict(conn.execute("SELECT SourceID, Name FROM SourceTable"))
        self.citations = {
            cid: (sid, name)
            for cid, sid, name in conn.execute("SELECT CitationID, SourceID, CitationName FROM CitationTable")
        }
        self.citation_links = defaultdict(list)
        for cid, otype, oid in conn.execute("SELECT CitationID, OwnerType, OwnerID FROM CitationLinkTable"):
            self.citation_links[cid].append((otype, oid))
        self.media = conn.execute(
            "SELECT MediaID, MediaType, MediaPath, MediaFile FROM MultimediaTable ORDER BY MediaID"
        ).fetchall()
        self.media_links = defaultdict(list)
        self.media_link_rows = conn.execute("SELECT LinkID, MediaID, OwnerType, OwnerID FROM MediaLinkTable").fetchall()
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
            oid for links in self.citation_links.values() for otype, oid in links if otype == OWNER_EVENT
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
        parts = PureWindowsPath(path[len(self.root):]).parts
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


class Checks(list):
    """A script's checks: (code, title, needs_scans, function), registered with @checks.add(...)."""

    def add(self, code: str, title: str, needs_scans: bool = False):
        def register(fn):
            self.append((code, title, needs_scans, fn))
            return fn

        return register


def run(doc: str, name: str, checks: Checks) -> int:
    """Run the checks on the file in argv[1]; write details to tmp/output/validate/, print a summary."""
    if len(sys.argv) < 2:
        print(doc)
        return 2
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"File not found: {path}")
        return 2
    scans = any(needs for _, _, needs, _ in checks)
    parser = argparse.ArgumentParser(prog=f"validate_{name}.py PATH_TO_RMTREE")
    parser.add_argument("--config", type=Path, help="settings file (default config.toml)")
    if scans:
        parser.add_argument("--scan-list", type=Path, help="file listing scan paths")
        parser.add_argument("--no-scans", action="store_true", help="skip disk checks")
    args = parser.parse_args(sys.argv[2:])
    cfg = load_config(args.config)

    disk = None
    if scans and not args.no_scans:
        if args.scan_list:
            lines = args.scan_list.read_text(encoding="utf-8").splitlines()
            disk = [line.strip().lstrip("﻿") for line in lines if line.strip()]
        else:
            disk = list_windows_files(cfg["scan_root"])

    conn = connect_readonly(path)
    try:
        tree = Tree(conn, cfg, disk)
        results = [
            (code, title, None if needs and disk is None else fn(tree)) for code, title, needs, fn in checks
        ]
    finally:
        conn.close()
    summary = [f"{'skipped' if lines is None else len(lines):>7}  {code:<30} {title}" for code, title, lines in results]

    with output_file(f"validate_{name}", "validate"):
        print(f"File: {path}")
        if scans:
            print(f"Scan files listed: {'skipped' if disk is None else len(disk)}")
        print()
        print("\n".join(summary))
        for code, title, lines in results:
            if lines:
                print(f"\n== {code}: {title} ({len(lines)})")
                for line in lines:
                    print(f"   {line}")
    print("\n".join(summary))
    return 0
