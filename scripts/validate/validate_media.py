"""Validate media (MultimediaTable, MediaLinkTable) and scan files. Read-only.

Scan checks compare the database with the files under scan_root (see config.example.toml). The
file list comes from Windows PowerShell unless --scan-list gives a file with one full Windows path
per line; --no-scans skips them.

Writes each media row with an issue to tmp/output/validate/<timestamp>_validate_media.txt and
prints a summary of counts.

Usage: python validate_media.py PATH_TO_RMTREE [--config FILE] [--scan-list FILE] [--no-scans]
"""

import sys
from collections import defaultdict
from pathlib import PureWindowsPath

from validate_common import (
    IMAGE_EXTENSIONS,
    MEDIA_FILE,
    MEDIA_IMAGE,
    OWNER_CITATION,
    OWNER_EVENT,
    OWNER_PERSON,
    OWNER_SOURCE,
    Checks,
    Tree,
    date_problem,
    media_path,
    run,
    sort_date_problem,
)

CHECKS = Checks()


@CHECKS.add("scan_not_in_db", "Scan files on disk not in the database", needs_scans=True)
def scan_not_in_db(t: Tree) -> list[str]:
    known = {media_path(p, f).lower() for _, _, p, f in t.media}
    return sorted(d for d in t.disk if t.is_scan(d) and d.lower() not in known)


@CHECKS.add("media_file_missing", "Media rows whose file is not on disk", needs_scans=True)
def media_file_missing(t: Tree) -> list[str]:
    on_disk = {d.lower() for d in t.disk}
    out = []
    for mid, _, path, file in t.media:
        full = media_path(path, file)
        if t.under_root(full) and full.lower() not in on_disk:
            out.append(f"{full} [M{mid}]")
    return out


@CHECKS.add("media_outside_root", "Media rows whose path is not under the scan folder")
def media_outside_root(t: Tree) -> list[str]:
    return [
        f"{media_path(path, file)} [M{mid}]"
        for mid, _, path, file in t.media
        if not t.under_root(media_path(path, file))
    ]


@CHECKS.add("media_unlinked", "Media not attached to anything")
def media_unlinked(t: Tree) -> list[str]:
    return [f"{media_path(path, file)} [M{mid}]" for mid, _, path, file in t.media if not t.media_links.get(mid)]


@CHECKS.add("media_not_on_citation", "Media attached to an event or source but no citation")
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


@CHECKS.add("media_type_mismatch", "PDF stored as Image, or image stored as File")
def media_type_mismatch(t: Tree) -> list[str]:
    out = []
    for mid, mtype, path, file in t.media:
        ext = PureWindowsPath(file or "").suffix.lower()
        if mtype == MEDIA_IMAGE and ext == ".pdf":
            out.append(f"{media_path(path, file)} [M{mid}] is Image")
        elif mtype == MEDIA_FILE and ext in IMAGE_EXTENSIONS:
            out.append(f"{media_path(path, file)} [M{mid}] is File")
    return out


@CHECKS.add("media_duplicate", "Same file in more than one media row")
def media_duplicate(t: Tree) -> list[str]:
    groups = defaultdict(list)
    for mid, _, path, file in t.media:
        groups[media_path(path, file).lower()].append((mid, media_path(path, file)))
    return [f"{rows[0][1]} [{', '.join(f'M{mid}' for mid, _ in rows)}]" for rows in groups.values() if len(rows) > 1]


@CHECKS.add("media_link_orphan", "Media links pointing to a missing record")
def media_link_orphan(t: Tree) -> list[str]:
    exists = {OWNER_PERSON: t.names, OWNER_EVENT: t.events_by_id, OWNER_SOURCE: t.sources,
              OWNER_CITATION: t.citations}
    media_ids = {row[0] for row in t.media}
    out = []
    for link_id, mid, otype, oid in t.media_link_rows:
        if mid not in media_ids:
            out.append(f"link {link_id}: media M{mid} missing")
        elif otype in exists and oid not in exists[otype]:
            out.append(f"link {link_id}: M{mid} -> owner type {otype} id {oid} missing")
    return out


@CHECKS.add("media_date_form", "Media dates that are not a well-formed encoded date")
def media_date_form(t: Tree) -> list[str]:
    return [
        f"{media_path(path, file)} [M{mid}] {date!r}: {problem}"
        for mid, path, file, date in t.conn.execute(
            "SELECT MediaID, MediaPath, MediaFile, Date FROM MultimediaTable ORDER BY MediaID")
        if (problem := date_problem(date))
    ]


@CHECKS.add("media_sort_date", "Media SortDate differs from the one worked out from the date")
def media_sort_date(t: Tree) -> list[str]:
    return [
        f"{media_path(path, file)} [M{mid}] {date}: {problem}"
        for mid, path, file, date, sort in t.conn.execute(
            "SELECT MediaID, MediaPath, MediaFile, Date, SortDate FROM MultimediaTable ORDER BY MediaID")
        if (problem := sort_date_problem(date, sort))
    ]


def main() -> int:
    return run(__doc__, "media", CHECKS)


if __name__ == "__main__":
    sys.exit(main())
