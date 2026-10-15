"""Attach a scan file to a citation.

Adds the file to MultimediaTable (or reuses its row if it is already there),
links it to the citation, and fills the citation's AccessDate field from the
file's last-modified date when that field exists and is empty. New rows copy the
values of existing citation scans (found in the database, not documentation):
  MultimediaTable  MediaType 1 image / 2 file (PDF and other non-images),
                   URL/Caption/RefNumber/Description '', Date '.',
                   SortDate 9223372036854775807, a JPEG thumbnail with
                   longest side 100 pixels
  MediaLinkTable   OwnerType 4 (citation), IsPrimary 1 if it is the
                   citation's first scan, Include1 1, others 0, no crop area,
                   Comments ''

Dry run by default: prints what would change. --apply writes it in one
transaction. RootsMagic must be closed, and the file must be a working copy.

Usage: python attach_scan.py PATH_TO_RMTREE CITATION_ID WINDOWS_FILE_PATH [--apply]
"""

import argparse
import sys
from pathlib import PureWindowsPath

from rmutils import (
    access_date_text,
    connect_readonly,
    connect_readwrite,
    db_path_arg,
    fields_blob,
    read_fields,
    template_fields,
    utc_mod_date,
    windows_file_modified,
    windows_thumbnail,
)

OWNER_CITATION = 4
MEDIA_IMAGE, MEDIA_FILE = 1, 2
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".tif", ".tiff", ".png", ".gif", ".bmp"}
NO_DATE = "."
NO_SORT_DATE = 9223372036854775807


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    parser = argparse.ArgumentParser(prog="attach_scan.py PATH_TO_RMTREE")
    parser.add_argument("citation", type=int)
    parser.add_argument("file")
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args(sys.argv[2:])

    scan = PureWindowsPath(args.file)
    folder, name = str(scan.parent), scan.name
    media_type = MEDIA_IMAGE if scan.suffix.lower() in IMAGE_EXTENSIONS else MEDIA_FILE

    conn = connect_readonly(path)
    try:
        citation = conn.execute(
            """SELECT c.CitationName, c.Fields, s.TemplateID FROM CitationTable c
               JOIN SourceTable s USING (SourceID) WHERE c.CitationID = ?""",
            (args.citation,),
        ).fetchone()
        if citation is None:
            print(f"Citation C{args.citation} not found")
            return 1
        old_name, blob, template_id = citation
        media = conn.execute(
            "SELECT MediaID FROM MultimediaTable WHERE MediaPath = ? COLLATE NOCASE"
            " AND MediaFile = ? COLLATE NOCASE ORDER BY MediaID",
            (folder, name),
        ).fetchone()
        media_id = media[0] if media else None
        if media_id and conn.execute(
            "SELECT 1 FROM MediaLinkTable WHERE MediaID = ? AND OwnerType = ? AND OwnerID = ?",
            (media_id, OWNER_CITATION, args.citation),
        ).fetchone():
            print(f"{scan} is already attached to citation C{args.citation}")
            return 1
        first_scan = not conn.execute(
            "SELECT 1 FROM MediaLinkTable WHERE OwnerType = ? AND OwnerID = ?",
            (OWNER_CITATION, args.citation),
        ).fetchone()
        citation_order = [n for n, is_cit in template_fields(conn, template_id) if is_cit]
    finally:
        conn.close()

    modified = windows_file_modified(str(scan))
    if modified is None:
        print(f"File not found on disk: {scan}")
        return 1

    fields = read_fields(blob)
    new_fields = dict(fields)
    if "AccessDate" in fields and not fields["AccessDate"]:
        new_fields["AccessDate"] = access_date_text(modified)
    new_name = "; ".join(new_fields.get(n, "") for n in citation_order) if citation_order else old_name

    thumbnail = windows_thumbnail(str(scan)) if media_type == MEDIA_IMAGE and not media_id else None

    print(f"Citation C{args.citation}")
    if media_id:
        print(f"   reuse media M{media_id}: {scan}")
    else:
        print(f"   add media: {scan}")
        preview = f"{len(thumbnail)} bytes" if thumbnail else "none"
        print(f"      MediaType {media_type}; Date '{NO_DATE}'; thumbnail {preview}")
    print(f"   link media -> citation C{args.citation} (OwnerType {OWNER_CITATION});"
          f" IsPrimary {int(first_scan)}; Include1 1")
    if new_fields != fields:
        print(f"   AccessDate: '{fields['AccessDate']}' -> '{new_fields['AccessDate']}'"
              f" (file last modified {modified})")
        print(f"   CitationName: '{old_name}' -> '{new_name}'")
    else:
        print("   AccessDate: unchanged")

    if not args.apply:
        print("Dry run: nothing changed.")
        return 0

    stamp = utc_mod_date()
    conn = connect_readwrite(path)
    try:
        if not media_id:
            media_id = conn.execute(
                """INSERT INTO MultimediaTable (MediaType, MediaPath, MediaFile, URL,
                       Thumbnail, Caption, RefNumber, Date, SortDate, Description, UTCModDate)
                   VALUES (?, ?, ?, '', ?, '', '', ?, ?, '', ?)""",
                (media_type, folder, name, thumbnail, NO_DATE, NO_SORT_DATE, stamp),
            ).lastrowid
        conn.execute(
            """INSERT INTO MediaLinkTable (MediaID, OwnerType, OwnerID, IsPrimary, Include1,
                   Include2, Include3, Include4, SortOrder, RectLeft, RectTop, RectRight,
                   RectBottom, Comments, UTCModDate)
               VALUES (?, ?, ?, ?, 1, 0, 0, 0, 0, 0, 0, 0, 0, '', ?)""",
            (media_id, OWNER_CITATION, args.citation, int(first_scan), stamp),
        )
        if new_fields != fields:
            conn.execute(
                "UPDATE CitationTable SET Fields = ?, CitationName = ?, UTCModDate = ?"
                " WHERE CitationID = ?",
                (fields_blob(new_fields, declaration=False), new_name, stamp, args.citation),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"Applied: media M{media_id} attached to citation C{args.citation}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
