"""Fetch the scans attached to citations and flag details that do not fit the scan forms (read-only).

The table and standards are in .claude/skills/rm-evaluate-scans/scan_forms.md (--table FILE for
another). Each scan takes the first row whose Name matches the source of a citation it is attached to:

  M1       Caption empty or not in the form; or its year differs from the Date's year
  M2       RefNumber empty or not in the form
  M3       Description empty or not in the form
  M4       no Date, or a Date whose form is not known
  G13      file name not in the form
  G19      the file is in an "unsure" or "Unsorted" folder
  L1       a PDF stored as Image, or an image stored as File
  SHARED   attached to more than one citation (G12: one media row per entry)
  NOROW    no row fits the scan

Writes each flagged scan to tmp/output/media/<timestamp>_evaluate_scans.txt and prints the counts
per source and flag. Fix with records/media.py edit (and files/file.py rename for G13).

Usage: python evaluate_scans.py PATH_TO_RMTREE (--source ID ... | --citation ID ... | --all) [--table FILE]
"""

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path, PureWindowsPath

from rmutils import PROJECT_DIR, connect_readonly, db_path_arg, event_sort_date, load_rows, output_file, wildcard

TABLE_FILE = PROJECT_DIR / ".claude" / "skills" / "rm-evaluate-scans" / "scan_forms.md"
OWNER_CITATION = 4
MEDIA_IMAGE, MEDIA_FILE = 1, 2
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".tif", ".tiff", ".png", ".gif", ".webp", ".bmp"}
CAPTION_YEAR = re.compile(r"– (\d{4})")


def forms(cell: str) -> list[re.Pattern] | None:
    cell = cell.strip("`")
    return None if cell in ("-", "") else [wildcard(v.strip().strip("`")) for v in cell.split("|")]


def check(flags: list, code: str, label: str, value: str, patterns) -> None:
    if patterns is None:
        return
    if not (value or "").strip():
        flags.append(f"{code} {label} is empty")
    elif not any(p.fullmatch(value) for p in patterns):
        shapes = " or ".join(repr(p.pattern.replace("(.+?)", "*").replace("\\", "")) for p in patterns)
        flags.append(f"{code} {label} {value[:70]!r} not in the form {shapes}")


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="evaluate_scans.py PATH_TO_RMTREE")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--source", type=int, action="append")
    which.add_argument("--citation", type=int, action="append")
    which.add_argument("--all", action="store_true")
    parser.add_argument("--table", type=Path, default=TABLE_FILE)
    args = parser.parse_args(sys.argv[2:])
    rows = load_rows(args.table, "Scan forms")

    conn = connect_readonly(path)
    try:
        links = conn.execute(
            "SELECT l.MediaID, c.CitationID, s.SourceID, s.Name FROM MediaLinkTable l JOIN CitationTable c"
            " ON l.OwnerType = ? AND l.OwnerID = c.CitationID JOIN SourceTable s USING (SourceID)"
            " ORDER BY l.MediaID", (OWNER_CITATION,)).fetchall()
        citations_of = defaultdict(list)
        for mid, cid, sid, source in links:
            citations_of[mid].append((cid, sid, source or ""))
        if args.all:
            chosen = sorted(citations_of)
        elif args.source:
            chosen = sorted({m for m, cits in citations_of.items() if any(s in args.source for _, s, _ in cits)})
        else:
            chosen = sorted({m for m, cits in citations_of.items() if any(c in args.citation for c, _, _ in cits)})
        media = {m: rest for m, *rest in conn.execute(
            "SELECT MediaID, MediaType, MediaPath, MediaFile, Caption, RefNumber, Description, Date FROM MultimediaTable")}
    finally:
        conn.close()
    if not chosen:
        print("No scans found")
        return 1

    results = []
    for mid in chosen:
        mtype, folder, file, caption, ref, description, date = media[mid]
        cits = citations_of[mid]
        flags = []
        row = next((r for r in rows for _, _, source in cits if any(p.fullmatch(source) for p in r["_patterns"])),
                   None)
        if row is None:
            flags.append("NOROW no row in scan_forms.md fits this scan")
        else:
            check(flags, "M1", "Caption", caption, forms(row["Caption"]))
            check(flags, "M2", "RefNumber", ref, forms(row["RefNumber"]))
            check(flags, "M3", "Description", description, forms(row["Description"]))
            name_forms = forms(row["File"])
            if name_forms and not any(p.fullmatch(file or "") for p in name_forms):
                flags.append(f"G13 file name {file!r} not in the form {row['File'].strip('`')!r}")
        if not date or date == ".":
            flags.append("M4 no Date")
        elif event_sort_date(date) is None:
            flags.append(f"M4 Date {date!r}: form not known")
        year = CAPTION_YEAR.search(caption or "")
        if year and date and date[3:7].isdigit() and date[3:7] != year.group(1):
            flags.append(f"M1 caption year {year.group(1)}, Date year {date[3:7]}")
        parts = {p.casefold() for p in PureWindowsPath(folder or "").parts}
        if {"unsure", "unsorted"} & parts:
            flags.append("G19 file in an unsure or Unsorted folder")
        ext = PureWindowsPath(file or "").suffix.lower()
        if (mtype == MEDIA_IMAGE and ext == ".pdf") or (mtype == MEDIA_FILE and ext in IMAGE_EXTENSIONS):
            flags.append(f"L1 {ext} stored as {'Image' if mtype == MEDIA_IMAGE else 'File'}")
        if len({c for c, _, _ in cits}) > 1:
            flags.append("SHARED on citations " + ", ".join(f"C{c}" for c, _, _ in cits))
        results.append((mid, folder, file, caption, cits, flags))

    with output_file("evaluate_scans", "media"):
        print(f"File: {path}\nTable: {args.table}\n")
        for mid, folder, file, caption, cits, flags in results:
            if flags or args.citation:
                print(f"M{mid}  {folder}\\{file}  ({', '.join(f'C{c} S{s}' for c, s, _ in cits)})")
                print(f"   Caption: {caption!r}")
                for flag in flags or ["(no flags)"]:
                    print(f"   ! {flag}")
                print()
    by_source = defaultdict(list)
    for result in results:
        by_source[(result[4][0][1], result[4][0][2])].append(result)
    for (sid, source), group in sorted(by_source.items()):
        counts = Counter(flag.split()[0] for r in group for flag in r[5])
        print(f"S{sid} '{source}': {len(group)} scans, {sum(1 for r in group if r[5])} flagged"
              + ("; " + ", ".join(f"{c} {n}" for c, n in sorted(counts.items())) if counts else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
