"""Validate citations (CitationTable). Read-only.

Writes each citation with an issue to tmp/output/validate/<timestamp>_validate_citation.txt and
prints a summary of counts. Links from citations are checked by validate_citation_link.py.

Usage: python validate_citation.py PATH_TO_RMTREE [--config FILE]
"""

import sys

from validate_common import OWNER_CITATION, Checks, Tree, run

CHECKS = Checks()


@CHECKS.add("citation_no_media", "Citations with no scan attached")
def citation_no_media(t: Tree) -> list[str]:
    with_media = {oid for links in t.media_links.values() for otype, oid in links if otype == OWNER_CITATION}
    out = []
    for cid in sorted(t.citations):
        if cid not in with_media:
            links = t.citation_links.get(cid, [])
            used = t.citation_owner(*links[0]) if links else "(not used)"
            more = f" (+{len(links) - 1} more)" if len(links) > 1 else ""
            out.append(f"{t.citation(cid)} - {used}{more}")
    return out


@CHECKS.add("citation_unused", "Citations not attached to anything")
def citation_unused(t: Tree) -> list[str]:
    return [t.citation(cid) for cid in sorted(t.citations) if not t.citation_links.get(cid)]


def main() -> int:
    return run(__doc__, "citation", CHECKS)


if __name__ == "__main__":
    sys.exit(main())
