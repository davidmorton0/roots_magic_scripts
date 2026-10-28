"""Validate sources (SourceTable). Read-only.

Writes each source with an issue to tmp/output/validate/<timestamp>_validate_source.txt and prints
a summary of counts.

Usage: python validate_source.py PATH_TO_RMTREE [--config FILE]
"""

import sys

from validate_common import Checks, Tree, run

CHECKS = Checks()


@CHECKS.add("source_unused", "Sources with no citations")
def source_unused(t: Tree) -> list[str]:
    used = {sid for sid, _ in t.citations.values()}
    return [f"{name} [S{sid}]" for sid, name in sorted(t.sources.items()) if sid not in used]


def main() -> int:
    return run(__doc__, "source", CHECKS)


if __name__ == "__main__":
    sys.exit(main())
