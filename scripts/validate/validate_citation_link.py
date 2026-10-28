"""Validate citation links (CitationLinkTable). Read-only.

Quality is three characters, as RootsMagic 12 writes them: information P/S/~, evidence D/I/N/~,
source O/X/~ ("~~~" not assessed, which is valid here).

Writes each link with an issue to tmp/output/validate/<timestamp>_validate_citation_link.txt and
prints a summary of counts.

Usage: python validate_citation_link.py PATH_TO_RMTREE [--config FILE]
"""

import re
import sys

from validate_common import OWNER_EVENT, OWNER_FAMILY, OWNER_NAME, OWNER_PERSON, Checks, Tree, run

CHECKS = Checks()
QUALITY = re.compile(r"[PS~][DIN~][OX~]")


@CHECKS.add("citation_link_orphan", "Citation links pointing to a missing citation or record")
def citation_link_orphan(t: Tree) -> list[str]:
    name_ids = {r[0] for r in t.conn.execute("SELECT NameID FROM NameTable")}
    exists = {OWNER_PERSON: t.names, OWNER_FAMILY: t.families, OWNER_EVENT: t.events_by_id, OWNER_NAME: name_ids}
    out = []
    for cid, links in sorted(t.citation_links.items()):
        for otype, oid in links:
            if cid not in t.citations:
                out.append(f"citation C{cid} missing (owner type {otype} id {oid})")
            elif otype in exists and oid not in exists[otype]:
                out.append(f"{t.citation(cid)} -> owner type {otype} id {oid} missing")
    return out


@CHECKS.add("citation_link_quality", "Citation links whose quality is not three valid characters")
def citation_link_quality(t: Tree) -> list[str]:
    return [
        f"link {link}: {t.citation(cid)} -> {t.citation_owner(otype, oid)} quality {quality!r}"
        for link, cid, otype, oid, quality in t.conn.execute(
            "SELECT LinkID, CitationID, OwnerType, OwnerID, Quality FROM CitationLinkTable ORDER BY LinkID")
        if not QUALITY.fullmatch(quality or "")
    ]


def main() -> int:
    return run(__doc__, "citation_link", CHECKS)


if __name__ == "__main__":
    sys.exit(main())
