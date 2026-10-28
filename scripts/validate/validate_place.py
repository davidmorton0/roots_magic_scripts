"""Validate places and place details (PlaceTable). Read-only. RootsMagic's temple list (PlaceType 1)
is not checked.

Writes each place with an issue to tmp/output/validate/<timestamp>_validate_place.txt and prints a
summary of counts.

Usage: python validate_place.py PATH_TO_RMTREE [--config FILE]
"""

import re
import sys
from collections import defaultdict

from validate_common import PLACE_DETAIL, PLACE_TEMPLE, Checks, Tree, run

CHECKS = Checks()


def place_key(name: str) -> list[str]:
    """Words of a place name, ignoring case, punctuation, "the" and a final s or 's."""
    words = re.sub(r"[^\w\s]", " ", name.casefold().replace("'s", "")).split()
    return [w.removesuffix("s") if len(w) > 3 else w for w in words if w != "the"]


@CHECKS.add("place_unused", "Places and place details used by no fact, FAN row or place detail")
def place_unused(t: Tree) -> list[str]:
    return [
        f"{name} [L{pid}]" + (" (detail)" if ptype == PLACE_DETAIL else "")
        for pid, ptype, name, _ in t.places
        if ptype != PLACE_TEMPLE and not t.used_places.get(pid)
    ]


@CHECKS.add("place_detail_similar", "Place details under one place with near-identical names")
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


def main() -> int:
    return run(__doc__, "place", CHECKS)


if __name__ == "__main__":
    sys.exit(main())
