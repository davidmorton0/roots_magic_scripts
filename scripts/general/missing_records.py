"""Checklists of records still to find, one file per record type (read-only on the tree).

People, by degree of separation from the root person (RootPerson in ConfigTable):
  degree 0  the root person and their direct ancestors
  degree n  brothers, sisters, spouses and children of the blood relatives of degree n-1
Spouses are listed but not followed further (their own relatives are not added). A person keeps the
first degree they are reached at.

A record is missing when the person was alive at the time and no citation from that record's
sources touches them (on their events, names, person, or their families and family events).
Alive: from the Birth (or Christen) to the Death (or Burial); with no Death or Burial, up to a
maximum age of 100. People with no Birth or Christen date are listed once per file, unchecked.
The country at a date is read from the place of the person's nearest dated event (default
England); records are only expected where the country kept them:
  births, marriages, deaths  England and Wales from Jul 1837, Scotland from 1855, Ireland births
                             and deaths from 1864, marriages from Apr 1845
  censuses                   England, Wales and Scotland 1841-1921; Ireland 1901, 1911; US
                             1850-1950 (not 1890); 1939 Register England and Wales
Marriages: one item per family of a blood relative (listed once), with the Marriage date, or
"date unknown" (with the first child's birth year when known). Deaths: a known Death with no
index citation, or "not in tree" with the years to search (last dated record to the Burial or age
100); someone born less than 100 years ago with no Death or Burial is taken as living.

Writes notes/missing/missing_birth_registers.md, missing_censuses.md, missing_1939_register.md,
missing_marriage_registers.md and missing_death_registers.md (or into --out DIR). The files are
rewritten on each run: an item drops out once its record is cited in the tree.

Usage: python missing_records.py PATH_TO_RMTREE --degree N [--out DIR]
"""

import argparse
import calendar
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import rmutils
from rmutils import PROJECT_DIR, connect_readonly, db_path_arg, person_names

OWNER_PERSON, OWNER_FAMILY, OWNER_EVENT, OWNER_NAME = 0, 1, 2, 7
FACT_BIRTH, FACT_DEATH, FACT_CHRISTEN, FACT_BURIAL, FACT_MARRIAGE = 1, 2, 3, 4, 300
MAX_AGE = 100
DEFAULT_COUNTRY = "England"

CENSUS_DAYS = {
    "England": {1841: (6, 6), 1851: (3, 30), 1861: (4, 7), 1871: (4, 2), 1881: (4, 3), 1891: (4, 5),
                1901: (3, 31), 1911: (4, 2), 1921: (6, 19)},
    "Ireland": {1901: (3, 31), 1911: (4, 2)},
    "US": {1850: (6, 1), 1860: (6, 1), 1870: (6, 1), 1880: (6, 1), 1900: (6, 1), 1910: (4, 15), 1920: (1, 1),
           1930: (4, 1), 1940: (4, 1), 1950: (4, 1)},
}
CENSUS_DAYS["Wales"] = CENSUS_DAYS["Scotland"] = CENSUS_DAYS["England"]
REGISTER_1939 = date(1939, 9, 29)
# country: (source name prefix, first date covered) per register type
REGISTERS = {
    "birth": {"England": ("Birth Register - UK", date(1837, 7, 1)), "Wales": ("Birth Register - UK", date(1837, 7, 1)),
              "Scotland": ("Birth Register - Scotland", date(1855, 1, 1)),
              "Ireland": ("Birth Register - Ireland", date(1864, 1, 1))},
    "marriage": {"England": ("Marriage Register - UK", date(1837, 7, 1)),
                 "Wales": ("Marriage Register - UK", date(1837, 7, 1)),
                 "Scotland": ("Marriage Register - Scotland", date(1855, 1, 1)),
                 "Ireland": ("Marriage Register - Ireland", date(1845, 4, 1))},
    "death": {"England": ("Death Register - UK", date(1837, 7, 1)), "Wales": ("Death Register - UK", date(1837, 7, 1)),
              "Scotland": ("Death Register - Scotland", date(1855, 1, 1)),
              "Ireland": ("Death Register - Ireland", date(1864, 1, 1))},
}
COUNTRY_WORDS = [
    ("Northern Ireland", "Ireland"), ("Ireland", "Ireland"), ("Scotland", "Scotland"), ("Wales", "Wales"),
    ("England", "England"), ("United States", "US"), ("USA", "US"),
    ("France", "Other"), ("Belgium", "Other"), ("Germany", "Other"), ("China", "Other"), ("Egypt", "Other"),
    ("Iceland", "Other"), ("At Sea", "Other"),
]
ENGLISH_COUNTIES = {"Berkshire", "Bristol", "Derbyshire", "Devon", "Dorset", "Essex", "Kent", "Lincoln",
                    "Lincolnshire", "London", "Middlesex", "Nottinghamshire", "Surrey", "Yorkshire"}
FILES = [
    ("birth", "missing_birth_registers.md", "Missing birth register (index) entries"),
    ("census", "missing_censuses.md", "Missing census entries"),
    ("1939", "missing_1939_register.md", "Missing 1939 Register entries"),
    ("marriage", "missing_marriage_registers.md", "Missing marriage register (index) entries"),
    ("death", "missing_death_registers.md", "Missing death register (index) entries"),
]


def country_of(place: str) -> str | None:
    for word, country in COUNTRY_WORDS:
        if re.search(rf"\b{word}\b", place):
            return country
    if any(p.strip() in ENGLISH_COUNTIES for p in place.split(",")):
        return "England"
    return None


def parse(rm_date: str, latest: bool = False) -> date | None:
    """A date from RootsMagic's encoded form: the first date, or for a range the last when latest.
    A missing month or day is taken as the start (or with latest, the end) of the year or month."""
    if not rm_date or len(rm_date) < 11 or rm_date[0] != "D":
        return None
    text = rm_date[14:22] if latest and rm_date[1] in "R-" and len(rm_date) >= 22 else rm_date[3:11]
    if not text.isdigit() or text[:4] == "0000":
        return None
    y, m, d = int(text[:4]), int(text[4:6]), int(text[6:])
    if m == 0:
        return date(y, 12, 31) if latest else date(y, 1, 1)
    if d == 0:
        return date(y, m, calendar.monthrange(y, m)[1] if latest else 1)
    return date(y, m, d)


def add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)


class Tree:
    def __init__(self, conn):
        self.conn = conn
        self.names = person_names(conn)
        self.places = dict(conn.execute("SELECT PlaceID, Name FROM PlaceTable"))
        self.families = {f: (fa, mo) for f, fa, mo in conn.execute("SELECT FamilyID, FatherID, MotherID FROM FamilyTable")}
        self.spouse_families = defaultdict(list)
        for f, (fa, mo) in self.families.items():
            for p in (fa, mo):
                if p:
                    self.spouse_families[p].append(f)
        self.children = defaultdict(list)
        self.parent_families = defaultdict(list)
        for child, fam in conn.execute("SELECT ChildID, FamilyID FROM ChildTable ORDER BY FamilyID, ChildOrder"):
            self.children[fam].append(child)
            self.parent_families[child].append(fam)
        self.events = defaultdict(list)  # (owner type, owner) -> [(event, fact, date, place)]
        for eid, fact, ot, oid, d, place in conn.execute(
                "SELECT EventID, EventType, OwnerType, OwnerID, Date, PlaceID FROM EventTable"
                " ORDER BY IsPrimary DESC, EventID"):
            self.events[(ot, oid)].append((eid, fact, d, place))
        sources = {cid: name for cid, name in conn.execute(
            "SELECT c.CitationID, s.Name FROM CitationTable c JOIN SourceTable s ON s.SourceID = c.SourceID")}
        self.cited = defaultdict(set)  # (owner type, owner) -> source names
        for cid, ot, oid in conn.execute("SELECT CitationID, OwnerType, OwnerID FROM CitationLinkTable"):
            if cid in sources:
                self.cited[(ot, oid)].add(sources[cid])
        self.name_owner = dict(conn.execute("SELECT NameID, OwnerID FROM NameTable"))

    def root(self) -> int:
        row = self.conn.execute("SELECT DataRec FROM ConfigTable WHERE RecID = 1").fetchone()
        text = row[0].decode("utf-8", "replace") if isinstance(row[0], bytes) else row[0]
        return int(re.search(r"<RootPerson>(\d+)</RootPerson>", text)[1])

    def name(self, pid: int) -> str:
        return f"P{pid} {self.names.get(pid, '(missing person)')}"

    def fact_events(self, owner_type: int, owner: int, fact: int) -> list[tuple]:
        return [e for e in self.events[(owner_type, owner)] if e[1] == fact]

    def first_date(self, pid: int, facts: tuple[int, ...], latest: bool = False) -> date | None:
        for fact in facts:
            for _, _, d, _ in self.fact_events(OWNER_PERSON, pid, fact):
                parsed = parse(d, latest)
                if parsed:
                    return parsed
        return None

    def sources_touching(self, pid: int) -> set[str]:
        out = set(self.cited[(OWNER_PERSON, pid)])
        for nid, owner in self.name_owner.items():
            if owner == pid:
                out |= self.cited[(OWNER_NAME, nid)]
        for eid, *_ in self.events[(OWNER_PERSON, pid)]:
            out |= self.cited[(OWNER_EVENT, eid)]
        for f in self.spouse_families[pid]:
            out |= self.cited[(OWNER_FAMILY, f)]
            for eid, *_ in self.events[(OWNER_FAMILY, f)]:
                out |= self.cited[(OWNER_EVENT, eid)]
        return out

    def dated_places(self, pid: int) -> list[tuple[date, str]]:
        """(date, place name) of the person's dated events with a place, and their families' events."""
        out = []
        keys = [(OWNER_PERSON, pid)] + [(OWNER_FAMILY, f) for f in self.spouse_families[pid]]
        for key in keys:
            for _, _, d, place in self.events[key]:
                parsed = parse(d)
                if parsed and place and self.places.get(place):
                    out.append((parsed, self.places[place]))
        return out

    def where(self, pid: int, when: date) -> tuple[str, str]:
        """(country, place name) of the dated event nearest to the date."""
        best = None
        for d, place in self.dated_places(pid):
            country = country_of(place)
            if country is None:
                continue
            gap = abs((d - when).days)
            if best is None or gap < best[0]:
                best = (gap, country, place)
        return (best[1], best[2]) if best else (DEFAULT_COUNTRY, "no place")


def people_by_degree(t: Tree, max_degree: int) -> list[tuple[int, int, str, bool]]:
    """(person, degree, how reached, is blood relative) in the order reached."""
    root = t.root()
    found = {root: (0, "root person", True)}
    order = [root]
    queue = [root]
    while queue:
        p = queue.pop(0)
        for fam in t.parent_families[p]:
            for parent, role in zip(t.families.get(fam, (0, 0)), ("father", "mother")):
                if parent and parent not in found:
                    found[parent] = (0, f"{role} of P{p}", True)
                    order.append(parent)
                    queue.append(parent)
    frontier = list(order)
    for degree in range(1, max_degree + 1):
        nxt = []
        for p in frontier:
            candidates = []
            for fam in t.parent_families[p]:
                candidates += [(s, f"sibling of P{p}", True) for s in t.children[fam] if s != p]
            for fam in t.spouse_families[p]:
                fa, mo = t.families[fam]
                candidates += [(s, f"spouse of P{p}", False) for s in (fa, mo) if s and s != p]
                candidates += [(ch, f"child of P{p}", True) for ch in t.children[fam]]
            for person, how, blood in candidates:
                if person not in found:
                    found[person] = (degree, how, blood)
                    order.append(person)
                    if blood:
                        nxt.append(person)
        frontier = nxt
    return [(p, *found[p]) for p in order]


def life(t: Tree, pid: int) -> tuple[date | None, date | None]:
    birth = t.first_date(pid, (FACT_BIRTH, FACT_CHRISTEN))
    death = t.first_date(pid, (FACT_DEATH, FACT_BURIAL), latest=True)
    return birth, death


def alive(birth: date, death: date | None, when: date) -> bool:
    if when < birth:
        return False
    return when <= death if death else when <= add_years(birth, MAX_AGE)


def span(birth: date | None, death: date | None) -> str:
    return f"{birth.year if birth else '?'}-{death.year if death else ''}"


def items_for(t: Tree, pid: int, blood: bool, listed_families: set, today: date) -> dict[str, list[str]]:
    birth, death = life(t, pid)
    out = defaultdict(list)
    if birth is None:
        return out
    sources = t.sources_touching(pid)

    def covered(prefixes) -> bool:
        return any(s.startswith(p) for s in sources for p in prefixes)

    # birth register
    country, place = t.where(pid, birth)
    reg = REGISTERS["birth"].get(country)
    if reg and birth >= reg[1]:
        cites = set()
        for eid, *_ in t.fact_events(OWNER_PERSON, pid, FACT_BIRTH):
            cites |= t.cited[(OWNER_EVENT, eid)]
        if not any(s.startswith(reg[0]) for s in cites):
            out["birth"].append(f"born {birth:%Y} ({country}; {place})")
    # censuses
    for c_country, days in CENSUS_DAYS.items():
        for year, (m, d) in days.items():
            when = date(year, m, d)
            if when > today or not alive(birth, death, when):
                continue
            here, place = t.where(pid, when)
            if here != c_country:
                continue
            prefixes = [f"Census - {c} {year}" for c in (["England", "Wales"] if here in ("England", "Wales")
                                                        else [here])]
            if not covered(prefixes):
                out["census"].append(f"{year} census ({here}; nearest place {place})")
    if alive(birth, death, REGISTER_1939) and REGISTER_1939 <= today:
        here, place = t.where(pid, REGISTER_1939)
        if here in ("England", "Wales") and not covered(["Register - England 1939"]):
            out["1939"].append(f"1939 Register (nearest place {place})")
    # marriages: families of blood relatives, once each
    if blood:
        for fam in t.spouse_families[pid]:
            if fam in listed_families:
                continue
            listed_families.add(fam)
            fa, mo = t.families[fam]
            partner = mo if pid == fa else fa
            marriages = t.fact_events(OWNER_FAMILY, fam, FACT_MARRIAGE)
            mdate = next((parse(d) for _, _, d, _ in marriages if parse(d)), None)
            cites = set()
            for eid, *_ in marriages:
                cites |= t.cited[(OWNER_EVENT, eid)]
            partner_text = t.name(partner) if partner else "unknown partner"
            if mdate:
                here, place = t.where(pid, mdate)
                reg = REGISTERS["marriage"].get(here)
                if reg and mdate >= reg[1] and not any(s.startswith(reg[0]) for s in cites):
                    out["marriage"].append(f"F{fam} with {partner_text}, married {mdate:%Y} ({here}; {place})")
            else:
                here, place = t.where(pid, add_years(birth, 25))
                reg = REGISTERS["marriage"].get(here)
                end = death or add_years(birth, MAX_AGE)
                if reg and end >= reg[1]:
                    births = [b for b in (life(t, ch)[0] for ch in t.children[fam]) if b]
                    hint = f", first child born {min(births).year}" if births else ""
                    out["marriage"].append(f"F{fam} with {partner_text}, date unknown{hint} ({here}; {place})")
    # death register
    deaths = t.fact_events(OWNER_PERSON, pid, FACT_DEATH)
    ddate = next((parse(d) for _, _, d, _ in deaths if parse(d)), None)
    if ddate:
        here, place = t.where(pid, ddate)
        reg = REGISTERS["death"].get(here)
        cites = set()
        for eid, *_ in deaths:
            cites |= t.cited[(OWNER_EVENT, eid)]
        if reg and ddate >= reg[1] and not any(s.startswith(reg[0]) for s in cites):
            out["death"].append(f"died {ddate:%Y} ({here}; {place})")
    elif death or add_years(birth, MAX_AGE) <= today:  # otherwise taken as living
        last = max([d for d, _ in t.dated_places(pid)] + [birth])
        end = death or add_years(birth, MAX_AGE)
        here, place = t.where(pid, last)
        reg = REGISTERS["death"].get(here)
        if reg and end >= reg[1]:
            limit = "buried" if death else "age 100"
            out["death"].append(f"Death not in tree: search {max(last, reg[1]).year}-{end.year} ({limit};"
                                f" {here}; last place {place})")
    return out


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="missing_records.py PATH_TO_RMTREE")
    parser.add_argument("--degree", type=int, required=True)
    parser.add_argument("--out", default=str(PROJECT_DIR / "notes" / "missing"))
    args = parser.parse_args(sys.argv[2:])
    today = rmutils.datetime.now().date()
    conn = connect_readonly(path)
    try:
        t = Tree(conn)
        people = people_by_degree(t, args.degree)
        listed_families: set = set()
        found = {kind: defaultdict(list) for kind, _, _ in FILES}
        undated = []
        for pid, degree, how, blood in people:
            if life(t, pid)[0] is None:
                undated.append((degree, pid, how))
                continue
            for kind, lines in items_for(t, pid, blood, listed_families, today).items():
                found[kind][degree] += [(pid, how, line) for line in lines]
        root = people[0][0]
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        for kind, filename, title in FILES:
            lines = [f"# {title}", "",
                     f"Generated {today:%Y-%m-%d} from `{path.name}`; root person {t.name(root)}; degrees 0-{args.degree}."
                     " Rewritten on each run (rm-missing-records skill): an item drops out once its record is cited.",
                     ""]
            total = 0
            for degree in range(args.degree + 1):
                rows = found[kind][degree]
                label = "direct ancestors" if degree == 0 else f"{degree} degree{'s' if degree > 1 else ''} of separation"
                lines += [f"## Degree {degree}: {label} ({len(rows)})", ""]
                for pid, how, text in rows:
                    birth, death = life(t, pid)
                    lines.append(f"- [ ] {t.name(pid)} ({span(birth, death)}; {how}): {text}")
                    total += 1
                lines.append("")
            if undated:
                lines += ["## No Birth or Christen date (not checked)", ""]
                lines += [f"- {t.name(pid)} (degree {degree}; {how})" for degree, pid, how in undated]
                lines.append("")
            (out_dir / filename).write_text("\n".join(lines), encoding="utf-8")
            print(f"{filename}: {total} items")
        print(f"{len(people)} people (degrees 0-{args.degree}), {len(undated)} with no Birth or Christen date")
        print(f"Written to {out_dir}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
