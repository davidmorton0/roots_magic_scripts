"""Get, create, edit or delete media (MultimediaTable) and its links to owners (MediaLinkTable).

  get     ID [ID ...] | --file TEXT | --path WINDOWS_FILE_PATH | --owner KIND:ID
                                    Print media with their links (read-only). --file matches part of
                                    the file name; --path is one file's full path (any case).
  create  --path WINDOWS_FILE_PATH [--set COLUMN=VALUE ...] [--date RM_DATE] [--type 1|2]
          [--no-thumbnail] [--link KIND:ID ...]
  edit    ID [--path WINDOWS_FILE_PATH] [--set COLUMN=VALUE ...] [--date RM_DATE] [--type 1|2]
          [--link KIND:ID ...] [--unlink KIND:ID ...]
  delete  ID [--with-links]

KIND is person, event, source or citation (MediaLinkTable OwnerType 0, 2, 3, 4). --set sets
Caption, RefNumber, Description or URL. --date is RootsMagic's encoded date text ("." for none) and
sets SortDate with it; a date form rmutils.sort_date does not know is refused. --type is 1 image or
2 file; the default is image for image extensions, else file. A new image gets a JPEG thumbnail
(longest side 100 pixels) unless --no-thumbnail. New rows copy existing citation scans: URL ''
and Date "." with SortDate 9223372036854775807; new links have IsPrimary 1 when the owner had no
media before, Include1 1, the others 0, no crop area, no comments.

--path on create must be a file on the drive and not already in a media row (the row is not
reused: link the existing row with edit --link). On edit it changes only the row (MediaPath,
MediaFile), not the file: use files/file.py to rename or move a file.

Refused when the file is not on the drive, an owner or media does not exist, a link exists already
(or does not, for --unlink), or (delete) the media is linked and --with-links is not given. Delete
removes the row and links, not the file.

MediaFile, Caption and RefNumber are in RMNOCASE indexes: run RootsMagic's rebuild indexes after
create or edit.

create, edit and delete are dry runs by default: they print what would change. --apply writes it in
one transaction. RootsMagic must be closed, and the file must be a working copy.

Usage: python media.py PATH_TO_RMTREE get|create|edit|delete ... [--apply]
"""

import argparse
import sys
from pathlib import Path, PureWindowsPath

from rmutils import (
    connect_readonly,
    db_path_arg,
    parse_assignments,
    sort_date,
    utc_mod_date,
    windows_file_modified,
    windows_thumbnail,
    write_changes,
)

OWNERS = {"person": (0, "PersonTable", "PersonID"), "event": (2, "EventTable", "EventID"),
          "source": (3, "SourceTable", "SourceID"), "citation": (4, "CitationTable", "CitationID")}
KIND_OF_CODE = {code: kind for kind, (code, _, _) in OWNERS.items()}
MEDIA_IMAGE, MEDIA_FILE = 1, 2
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".tif", ".tiff", ".png", ".gif", ".bmp"}
NO_DATE = "."
NO_SORT_DATE = 9223372036854775807
SET_COLUMNS = ("Caption", "RefNumber", "Description", "URL")


def parse_owner(text: str, option: str, problems: list[str]) -> tuple[str, int] | None:
    kind, _, owner = text.partition(":")
    if kind not in OWNERS or not owner.isdigit():
        problems.append(f"{option} {text!r} is not KIND:ID (kind {', '.join(OWNERS)})")
        return None
    return kind, int(owner)


def check_sets(sets: dict[str, str], problems: list[str]) -> None:
    for column in [c for c in sets if c not in SET_COLUMNS]:
        problems.append(f"--set {column!r} is not one of {', '.join(SET_COLUMNS)}")
        del sets[column]


def date_values(date_text: str | None, problems: list[str]) -> dict:
    """Date and SortDate columns for --date."""
    if date_text is None:
        return {}
    sort = NO_SORT_DATE if date_text == NO_DATE else sort_date(date_text)
    if sort is None:
        problems.append(f"--date {date_text!r}: SortDate not known for this form of date")
        return {}
    return {"Date": date_text, "SortDate": sort}


def split_path(text: str) -> tuple[str, str]:
    scan = PureWindowsPath(text)
    return str(scan.parent), scan.name


def media_type_of(text: str) -> int:
    return MEDIA_IMAGE if PureWindowsPath(text).suffix.lower() in IMAGE_EXTENSIONS else MEDIA_FILE


def check_owner(conn, owner: tuple[str, int], problems: list[str]) -> bool:
    _, table, key = OWNERS[owner[0]]
    if conn.execute(f"SELECT 1 FROM {table} WHERE {key} = ?", (owner[1],)).fetchone():
        return True
    problems.append(f"{owner[0]} {owner[1]} not found")
    return False


def insert_link(conn, media: int, owner: tuple[str, int], stamp: float) -> None:
    code = OWNERS[owner[0]][0]
    first = not conn.execute("SELECT 1 FROM MediaLinkTable WHERE OwnerType = ? AND OwnerID = ?",
                             (code, owner[1])).fetchone()
    conn.execute(
        "INSERT INTO MediaLinkTable (MediaID, OwnerType, OwnerID, IsPrimary, Include1, Include2, Include3,"
        " Include4, SortOrder, RectLeft, RectTop, RectRight, RectBottom, Comments, UTCModDate)"
        " VALUES (?, ?, ?, ?, 1, 0, 0, 0, 0, 0, 0, 0, 0, '', ?)", (media, code, owner[1], int(first), stamp))


def get(path: Path, args) -> int:
    problems = []
    owner = parse_owner(args.owner, "--owner", problems) if args.owner else None
    if problems:
        print(problems[0])
        return 1
    conn = connect_readonly(path)
    try:
        if args.ids:
            ids = args.ids
        elif owner:
            ids = [r[0] for r in conn.execute(
                "SELECT MediaID FROM MediaLinkTable WHERE OwnerType = ? AND OwnerID = ? ORDER BY LinkID",
                (OWNERS[owner[0]][0], owner[1]))]
        elif args.path:
            ids = [r[0] for r in conn.execute(
                "SELECT MediaID FROM MultimediaTable WHERE lower(MediaPath) = lower(?) AND lower(MediaFile) = lower(?)"
                " ORDER BY MediaID", split_path(args.path))]
        else:
            ids = [r[0] for r in conn.execute(
                "SELECT MediaID FROM MultimediaTable WHERE MediaFile LIKE ? ORDER BY MediaID",
                (f"%{args.file}%",))]
        if not ids:
            print("No media found")
            return 1
        for mid in ids:
            row = conn.execute(
                "SELECT MediaType, MediaPath, MediaFile, URL, length(Thumbnail), Caption, RefNumber, Date, SortDate,"
                " Description, UTCModDate FROM MultimediaTable WHERE MediaID = ?", (mid,)).fetchone()
            if row is None:
                print(f"M{mid} not found")
                return 1
            kind, folder, file, url, thumb, caption, ref, date_, sort, description, stamp = row
            print(f"M{mid}  {folder}\\{file}  (type {kind}, thumbnail {thumb or 0} bytes)")
            for label, value in (("URL", url), ("Caption", caption), ("RefNumber", ref),
                                 ("Description", description)):
                if value:
                    print(f"   {label}: {value!r}")
            print(f"   Date: {date_}  SortDate: {sort}  UTCModDate: {stamp}")
            for link, owner_type, owner_id, primary in conn.execute(
                    "SELECT LinkID, OwnerType, OwnerID, IsPrimary FROM MediaLinkTable WHERE MediaID = ?"
                    " ORDER BY LinkID", (mid,)):
                print(f"   link L{link} -> {KIND_OF_CODE.get(owner_type, f'type {owner_type}')} {owner_id}"
                      f" (IsPrimary {primary})")
    finally:
        conn.close()
    return 0


def create(path: Path, args) -> int:
    problems = []
    sets = parse_assignments(args.set, "--set", problems)
    check_sets(sets, problems)
    values = date_values(args.date, problems)
    owners = [o for o in (parse_owner(t, "--link", problems) for t in args.link) if o]
    folder, name = split_path(args.path)
    media_type = args.type or media_type_of(args.path)
    modified = windows_file_modified(args.path)
    if modified is None:
        problems.append(f"file not found on disk: {args.path}")
    thumbnail = windows_thumbnail(args.path) if modified and media_type == MEDIA_IMAGE and not args.no_thumbnail \
        else None

    conn = connect_readonly(path)
    try:
        same = conn.execute("SELECT MediaID FROM MultimediaTable WHERE lower(MediaPath) = lower(?)"
                            " AND lower(MediaFile) = lower(?)", (folder, name)).fetchone()
        if same:
            problems.append(f"M{same[0]} already uses {args.path}")
        for owner in owners:
            check_owner(conn, owner, problems)
    finally:
        conn.close()

    print(f"New media: {args.path} (type {media_type}, thumbnail {len(thumbnail) if thumbnail else 0} bytes)")
    for column, value in {**sets, **values}.items():
        print(f"   {column}: {value!r}")
    for kind, owner in owners:
        print(f"   link -> {kind} {owner}")
    if problems:
        print("Refused:\n   " + "\n   ".join(problems))
        return 1
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()

    def write(conn) -> int:
        media = conn.execute(
            "INSERT INTO MultimediaTable (MediaType, MediaPath, MediaFile, URL, Thumbnail, Caption, RefNumber,"
            " Date, SortDate, Description, UTCModDate) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (media_type, folder, name, sets.get("URL", ""), thumbnail, sets.get("Caption", ""),
             sets.get("RefNumber", ""), values.get("Date", NO_DATE), values.get("SortDate", NO_SORT_DATE),
             sets.get("Description", ""), stamp)).lastrowid
        for owner in owners:
            insert_link(conn, media, owner, stamp)
        return media

    print(f"Applied: media M{write_changes(path, write)}. Run RootsMagic's rebuild indexes.")
    return 0


def edit(path: Path, args) -> int:
    problems = []
    changes = dict(parse_assignments(args.set, "--set", problems))
    check_sets(changes, problems)
    changes.update(date_values(args.date, problems))
    if args.type:
        changes["MediaType"] = args.type
    if args.path:
        changes["MediaPath"], changes["MediaFile"] = split_path(args.path)
        if windows_file_modified(args.path) is None:
            problems.append(f"file not found on disk: {args.path}")
    add = [o for o in (parse_owner(t, "--link", problems) for t in args.link) if o]
    remove = [o for o in (parse_owner(t, "--unlink", problems) for t in args.unlink) if o]
    if not (changes or add or remove):
        problems.append("nothing to change")

    conn = connect_readonly(path)
    try:
        columns = list(changes) or ["Caption"]
        row = conn.execute("SELECT " + ", ".join(columns) + " FROM MultimediaTable WHERE MediaID = ?",
                           (args.id,)).fetchone()
        if row is None:
            print(f"M{args.id} not found")
            return 1
        old = dict(zip(columns, row))
        if args.path:
            clash = conn.execute("SELECT MediaID FROM MultimediaTable WHERE lower(MediaPath) = lower(?)"
                                 " AND lower(MediaFile) = lower(?) AND MediaID <> ?",
                                 (*split_path(args.path), args.id)).fetchone()
            if clash:
                problems.append(f"M{clash[0]} already uses {args.path}")
        for owner in add:
            if check_owner(conn, owner, problems) and conn.execute(
                    "SELECT 1 FROM MediaLinkTable WHERE MediaID = ? AND OwnerType = ? AND OwnerID = ?",
                    (args.id, OWNERS[owner[0]][0], owner[1])).fetchone():
                problems.append(f"M{args.id} is already linked to {owner[0]} {owner[1]}")
        unlink_ids = []
        for owner in remove:
            link = conn.execute("SELECT LinkID FROM MediaLinkTable WHERE MediaID = ? AND OwnerType = ?"
                                " AND OwnerID = ?", (args.id, OWNERS[owner[0]][0], owner[1])).fetchone()
            if link:
                unlink_ids.append(link[0])
            else:
                problems.append(f"M{args.id} is not linked to {owner[0]} {owner[1]}")
    finally:
        conn.close()

    print(f"M{args.id}:")
    for column, value in changes.items():
        print(f"   {column}: {old[column]!r} -> {value!r}")
    for kind, owner in add:
        print(f"   link -> {kind} {owner}")
    for kind, owner in remove:
        print(f"   unlink from {kind} {owner}")
    if problems:
        print("Refused:\n   " + "\n   ".join(problems))
        return 1
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()

    def write(conn) -> None:
        assignments = {**changes, "UTCModDate": stamp}
        conn.execute("UPDATE MultimediaTable SET " + ", ".join(f"{c} = ?" for c in assignments)
                     + " WHERE MediaID = ?", [*assignments.values(), args.id])
        for link in unlink_ids:
            conn.execute("DELETE FROM MediaLinkTable WHERE LinkID = ?", (link,))
        for owner in add:
            insert_link(conn, args.id, owner, stamp)

    write_changes(path, write)
    print(f"Applied: media M{args.id} changed. Run RootsMagic's rebuild indexes.")
    return 0


def delete(path: Path, args) -> int:
    conn = connect_readonly(path)
    try:
        row = conn.execute("SELECT MediaPath, MediaFile FROM MultimediaTable WHERE MediaID = ?",
                           (args.id,)).fetchone()
        links = conn.execute("SELECT COUNT(*) FROM MediaLinkTable WHERE MediaID = ?", (args.id,)).fetchone()[0]
    finally:
        conn.close()
    if row is None:
        print(f"M{args.id} not found")
        return 1
    print(f"Delete media M{args.id} {row[0]}\\{row[1]}: {links} links (the file is not deleted)")
    if links and not args.with_links:
        print(f"Refused: {links} links; give --with-links to delete them too")
        return 1
    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    def write(conn) -> None:
        conn.execute("DELETE FROM MediaLinkTable WHERE MediaID = ?", (args.id,))
        conn.execute("DELETE FROM MultimediaTable WHERE MediaID = ?", (args.id,))

    write_changes(path, write)
    print(f"Applied: media M{args.id} deleted.")
    return 0


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="media.py PATH_TO_RMTREE")
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("get")
    p.add_argument("ids", nargs="*", type=int)
    p.add_argument("--file")
    p.add_argument("--path")
    p.add_argument("--owner")
    p.set_defaults(run=get)

    p = commands.add_parser("create")
    p.add_argument("--path", required=True)
    p.add_argument("--no-thumbnail", action="store_true")
    p.set_defaults(run=create)

    p = commands.add_parser("edit")
    p.add_argument("id", type=int)
    p.add_argument("--path")
    p.add_argument("--unlink", action="append", default=[])
    p.set_defaults(run=edit)

    p = commands.add_parser("delete")
    p.add_argument("id", type=int)
    p.add_argument("--with-links", action="store_true")
    p.set_defaults(run=delete)

    for name in ("create", "edit"):
        sub = commands.choices[name]
        sub.add_argument("--set", action="append", default=[])
        sub.add_argument("--date")
        sub.add_argument("--type", type=int, choices=(MEDIA_IMAGE, MEDIA_FILE))
        sub.add_argument("--link", action="append", default=[])
    for name in ("create", "edit", "delete"):
        commands.choices[name].add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])
    if args.command == "get" and not (args.ids or args.file or args.path or args.owner):
        parser.error("get needs media IDs, --file, --path or --owner")
    return args.run(path, args)


if __name__ == "__main__":
    sys.exit(main())
