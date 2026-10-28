"""Shared helpers for RootsMagic .rmtree (SQLite) scripts."""

import base64
import re
import sqlite3
import subprocess
import sys
import tomllib
import uuid
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stdout
from datetime import date, datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

PROJECT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_DIR / "tmp" / "output"


def rmnocase(a: str, b: str) -> int:
    """Stand-in for RootsMagic's RMNOCASE collation: case-insensitive compare."""
    a, b = a.casefold(), b.casefold()
    return (a > b) - (a < b)


def connect_readonly(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    conn.create_collation("RMNOCASE", rmnocase)
    return conn


def connect_readwrite(path: Path) -> sqlite3.Connection:
    """Writable connection with explicit transactions (caller commits or rolls back)."""
    conn = sqlite3.connect(
        f"{path.resolve().as_uri()}?mode=rw", uri=True, autocommit=False
    )
    conn.create_collation("RMNOCASE", rmnocase)
    return conn


# CitationLinkTable owner kind -> (OwnerType, table, key column)
OWNER_TYPES = {"person": (0, "PersonTable", "PersonID"), "family": (1, "FamilyTable", "FamilyID"),
               "event": (2, "EventTable", "EventID"), "name": (7, "NameTable", "NameID")}


NO_DATE = "."
NO_SORT_DATE = 9223372036854775807


def event_sort_date(date_text: str) -> int | None:
    """SortDate for an event/media date: the no-date value for ".", else sort_date (None if not known)."""
    return NO_SORT_DATE if date_text == NO_DATE else sort_date(date_text)


def reverse_name(name: str) -> str:
    """Sort name of a place: the comma-separated parts in reverse order."""
    return ", ".join(part.strip() for part in reversed(name.split(",")))


def unique_id() -> str:
    """PersonTable.UniqueID: 32 hex digits plus a 4-digit checksum (as the one-off person scripts)."""
    guid = uuid.uuid4().hex.upper()
    a = b = 0
    for byte in bytes.fromhex(guid):
        a = (a + byte) % 256
        b = (b + a) % 256
    return f"{guid}{a:02X}{b:02X}"


def stop_unless_applying(problems: list[str], apply: bool) -> int | None:
    """Print refusals or the dry-run line; return the exit code to stop with, or None to write."""
    if problems:
        print("Refused:\n   " + "\n   ".join(problems))
        return 1
    if not apply:
        print("Dry run: nothing changed.")
        return 0
    return None


def write_changes(path: Path, write):
    """Run write(conn) in one transaction on the file: commit, or roll back on error."""
    conn = connect_readwrite(path)
    try:
        result = write(conn)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def parse_assignments(items: list[str], option: str, problems: list[str]) -> dict[str, str]:
    """NAME=VALUE items -> dict; items without "=" are added to problems."""
    result = {}
    for item in items:
        name, sep, value = item.partition("=")
        if not sep:
            problems.append(f"{option} {item!r} is not NAME=VALUE")
        result[name] = value
    return result


def utc_mod_date() -> float:
    """Current UTC time as RootsMagic's UTCModDate: days since 1899-12-30."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return (now - datetime(1899, 12, 30)).total_seconds() / 86400


def read_fields(blob: bytes | str | None) -> dict[str, str]:
    """Field name -> value from a SourceTable/CitationTable Fields XML blob."""
    text = blob.decode("utf-8") if isinstance(blob, bytes) else (blob or "")
    text = text.lstrip("﻿").strip()
    if not text:
        return {}
    root = ET.fromstring(text.encode("utf-8"))
    return {f.findtext("Name"): f.findtext("Value") or "" for f in root.iter("Field")}


def template_fields(conn: sqlite3.Connection, template_id: int) -> list[tuple[str, bool]]:
    """(field name, is citation field) in template order; [] if the template is missing."""
    row = conn.execute(
        "SELECT FieldDefs FROM SourceTemplateTable WHERE TemplateID = ?", (template_id,)
    ).fetchone()
    if not row or not row[0]:
        return []
    text = row[0].decode("utf-8") if isinstance(row[0], bytes) else row[0]
    root = ET.fromstring(text.lstrip("﻿").encode("utf-8"))
    return [
        (f.findtext("FieldName"), f.findtext("CitationField") == "True")
        for f in root.iter("Field")
    ]


def sort_date(rm_date: str) -> int | None:
    """SortDate RootsMagic gives a date string, or None for forms not worked out.

    Fitted to every date in the tree (2026-10-15), not documented:
      single  D.+YYYYMMDD..+00000000..   first + 17178820620  (1,316 dates)
      before  DB+YYYYMMDD..+00000000..   single - 12          (one RootsMagic example)
      after   DA+YYYYMMDD..+00000000..   single + 1047571     (one RootsMagic example, 2026-10-22)
      range   D-+YYYYMMDD..+YYYYMMDD..   first + second + 21  (363 dates)
      between DR+YYYYMMDD..+YYYYMMDD..   first + second + 15  (157 dates)
    first = (Y+10000)<<49 | M<<45 | D<<39; second = (Y+10000)<<20 | M<<16 | D<<10.
    An "about" qualifier (character 12) does not change it. Dates with no year
    (YYYY 0000) and double-dated years ("/" after a date) sort differently and
    return None.
    """
    if len(rm_date) < 24 or rm_date[0] != "D" or rm_date[2] != "+" or rm_date[13] != "+":
        return None
    a, b = rm_date[3:11], rm_date[14:22]
    if not (a.isdigit() and b.isdigit()) or a[:4] == "0000" or "/" in (rm_date[11], rm_date[22]):
        return None
    y1, m1, d1 = int(a[:4]), int(a[4:6]), int(a[6:])
    y2, m2, d2 = int(b[:4]), int(b[4:6]), int(b[6:])
    first = ((y1 + 10000) << 49) | (m1 << 45) | (d1 << 39)
    second = ((y2 + 10000) << 20) | (m2 << 16) | (d2 << 10)
    kind = rm_date[1]
    if kind in ".BA" and b == "00000000":
        return first + 17178820620 + {".": 0, "B": -12, "A": 1047571}[kind]
    if kind == "-":
        return first + second + 21
    if kind == "R":
        return first + second + 15
    return None


def access_date_text(day: date) -> str:
    """Date as written in existing citations' AccessDate, e.g. '7 August 2020'."""
    return f"{day.day} {day:%B %Y}"


def fields_blob(fields: dict[str, str], declaration: bool) -> bytes:
    """Fields XML in RootsMagic's layout.

    Source rows start with a byte-order mark and an XML declaration and end
    with a newline; citation rows have neither (as found in existing rows).
    """
    body = "".join(
        f"<Field><Name>{escape(name)}</Name><Value>{escape(value)}</Value></Field>"
        for name, value in fields.items()
    )
    xml = f"<Root><Fields>{body}</Fields></Root>"
    if declaration:
        xml = f'﻿<?xml version="1.0" encoding="UTF-8"?>\n{xml}\n'
    return xml.encode("utf-8")


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def full_name(surname, given, prefix, suffix) -> str:
    parts = [prefix, given, surname]
    name = " ".join(p for p in parts if p)
    if suffix:
        name += f", {suffix}"
    return name or "(no primary name)"


def person_names(conn: sqlite3.Connection) -> dict[int, str]:
    """PersonID -> primary name, for every person."""
    rows = conn.execute(
        """SELECT p.PersonID, n.Surname, n.Given, n.Prefix, n.Suffix
           FROM PersonTable p
           LEFT JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1"""
    )
    return {pid: full_name(*rest) for pid, *rest in rows}


def _ps_literal(text: str) -> str:
    """text as a single-quoted PowerShell string."""
    return "'" + text.replace("'", "''") + "'"


def _powershell(script: str) -> list[str]:
    """Run a Windows PowerShell script; return its non-blank output lines.

    Used because Windows drives such as Google Drive's H: are not visible
    from WSL.
    """
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            f"[Console]::OutputEncoding = [Text.Encoding]::UTF8; {script}",
        ],
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    return [
        line.strip().lstrip("﻿")
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def _windows_file_lines(root: str, per_file: str) -> list[str]:
    """One output line per file under root; per_file is run for each file ($_)."""
    return _powershell(
        f"Get-ChildItem -LiteralPath {_ps_literal(root)} -Recurse -File"
        f" | ForEach-Object {{ {per_file} }}"
    )


def windows_file_modified(path: str) -> date | None:
    """Last-modified date of one Windows file, or None if it does not exist."""
    lines = _powershell(
        f"$f = Get-Item -LiteralPath {_ps_literal(path)} -ErrorAction SilentlyContinue; "
        "if ($f) { $f.LastWriteTime.ToString('yyyy-MM-dd') }; exit 0"
    )
    return date.fromisoformat(lines[0]) if lines else None


def rename_windows_file(path: str, new_name: str) -> None:
    """Rename one Windows file in its folder; PowerShell's error stops the call."""
    _powershell(
        f"Rename-Item -LiteralPath {_ps_literal(path)} -NewName {_ps_literal(new_name)}"
        " -ErrorAction Stop"
    )


def move_windows_file(path: str, new_path: str) -> None:
    """Move one Windows file to another folder (created if missing); refused if new_path exists."""
    folder = new_path.rpartition("\\")[0]
    _powershell(
        f"New-Item -ItemType Directory -Force -Path {_ps_literal(folder)} | Out-Null; "
        f"if (Test-Path -LiteralPath {_ps_literal(new_path)}) {{ throw 'target exists' }}; "
        f"Move-Item -LiteralPath {_ps_literal(path)} -Destination {_ps_literal(new_path)} -ErrorAction Stop"
    )


def rootsmagic_running() -> bool:
    """True if a RootsMagic process is running on Windows."""
    return bool(_powershell("Get-Process *RootsMagic* -ErrorAction SilentlyContinue | Select-Object -First 1 Id"))


def windows_file_hash(path: str) -> str | None:
    """SHA-256 of one Windows file (upper-case hex, as Get-FileHash gives), or None if missing."""
    lines = _powershell(
        f"if (Test-Path -LiteralPath {_ps_literal(path)}) "
        f"{{ (Get-FileHash -LiteralPath {_ps_literal(path)} -Algorithm SHA256).Hash }}; exit 0"
    )
    return lines[0] if lines else None


def copy_windows_file(source: str, target: str) -> None:
    """Copy one file between Windows paths, overwriting; PowerShell's error stops the call."""
    _powershell(f"Copy-Item -LiteralPath {_ps_literal(source)} -Destination {_ps_literal(target)} -Force"
                " -ErrorAction Stop")


def windows_path(path: Path) -> str:
    """A WSL path as Windows sees it (\\\\wsl.localhost\\...), from wslpath."""
    return subprocess.run(["wslpath", "-w", str(path.resolve())], capture_output=True, encoding="utf-8",
                          check=True).stdout.strip()


def windows_thumbnail(path: str, size: int = 100) -> bytes:
    """JPEG preview of a Windows image file, longest side `size` pixels.

    Matches the thumbnails RootsMagic stores in MultimediaTable (JPEG or PNG,
    longest side 100 pixels, as found in existing rows).
    """
    lines = _powershell(
        "Add-Type -AssemblyName System.Drawing; "
        f"$src = [System.Drawing.Image]::FromFile({_ps_literal(path)}); "
        f"$s = [Math]::Min({size} / $src.Width, {size} / $src.Height); "
        "$w = [Math]::Max(1, [int][Math]::Round($src.Width * $s)); "
        "$h = [Math]::Max(1, [int][Math]::Round($src.Height * $s)); "
        "$bmp = New-Object System.Drawing.Bitmap $w, $h; "
        "$g = [System.Drawing.Graphics]::FromImage($bmp); "
        "$g.InterpolationMode = 'HighQualityBicubic'; "
        "$g.DrawImage($src, 0, 0, $w, $h); "
        "$ms = New-Object System.IO.MemoryStream; "
        "$bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Jpeg); "
        "[Convert]::ToBase64String($ms.ToArray()); "
        "$g.Dispose(); $bmp.Dispose(); $src.Dispose()"
    )
    return base64.b64decode(lines[0])


def list_windows_files(root: str) -> list[str]:
    """Full Windows paths of every file under root."""
    return _windows_file_lines(root, "$_.FullName")


def list_windows_files_with_dates(root: str) -> list[tuple[str, date]]:
    """(full Windows path as spelled on disk, last-modified date) for every file under root.

    Last-modified, not creation: creation dates show when files were copied to
    Google Drive (mostly 2020-01-19), not when they were downloaded.
    '|' separates path and date; Windows does not allow it in file names.
    """
    files = []
    for line in _windows_file_lines(
        root, "$_.FullName + '|' + $_.LastWriteTime.ToString('yyyy-MM-dd')"
    ):
        path, _, modified = line.rpartition("|")
        files.append((path, date.fromisoformat(modified)))
    return files


def list_windows_file_dates(root: str) -> dict[str, date]:
    """Lower-cased full Windows path -> last-modified date, for every file under root."""
    return {path.lower(): modified for path, modified in list_windows_files_with_dates(root)}


def markdown_table(path: Path, heading: str) -> list[dict[str, str]]:
    """Rows of the first table under '## heading' as {column: cell}; '\\|' in a cell is a '|'."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == f"## {heading}")
    rows = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        if line.startswith("|"):
            rows.append([c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]])
    return [dict(zip(rows[0], row)) for row in rows[2:]]


def field_values(cell: str) -> dict[str, list[str]]:
    """'A=x; B=y|z' -> {'A': ['x'], 'B': ['y', 'z']}. A value may hold "; " itself: a new field
    starts only where "; " is followed by a name and "="."""
    values = {}
    for item in filter(None, (f.strip() for f in re.split(r";\s+(?=\w+=)", cell))):
        name, _, value = item.partition("=")
        values[name.strip()] = value.split("|")
    return values


def condition_holds(condition: str, fields: dict[str, str], text: str = "") -> bool:
    """A table condition "Field~regex" (Field "Text" is the transcription) against a citation; "-" or "" holds.
    SpecificItem falls back to Page, so one condition fits template 6 and free-form citations."""
    if not condition or condition == "-":
        return True
    name, _, regex = condition.partition("~")
    value = text if name == "Text" else fields.get(name) or (fields.get("Page", "") if name == "SpecificItem" else "")
    return re.search(regex, value or "") is not None


def first_row(rows: list[dict], source_name: str, fields: dict[str, str] | None = None, text: str = "",
              extra=None) -> dict | None:
    """The first table row whose Name patterns match the source name, whose Condition holds (if the
    table has one) and for which extra(row) is true (if given)."""
    for row in rows:
        if not any(p.fullmatch(source_name) for p in row["_patterns"]):
            continue
        if "Condition" in row and not condition_holds(row["Condition"], fields or {}, text):
            continue
        if extra is None or extra(row):
            return row
    return None


def load_rows(path: Path, heading: str, column: str = "Name") -> list[dict]:
    """markdown_table rows with their name-pattern column compiled as "_patterns"."""
    rows = markdown_table(path, heading)
    for row in rows:
        row["_patterns"] = name_patterns(row[column])
    return rows


def name_patterns(text: str) -> list[re.Pattern]:
    """Patterns from a cell such as "`* - Ancestry` or `Census - *`": `*` stands for any text."""
    return [wildcard(p.strip().strip("`")) for p in text.split(" or ")]


def wildcard(text: str) -> re.Pattern:
    """A pattern in which each `*` stands for any text (captured), matched with fullmatch."""
    return re.compile("".join("(.+?)" if part == "*" else re.escape(part) for part in re.split(r"(\*)", text)),
                      re.DOTALL)


def load_config(path: Path | None = None) -> dict:
    """Settings from config.toml, or config.example.toml if that is missing."""
    if path is None:
        local = PROJECT_DIR / "config.toml"
        path = local if local.is_file() else PROJECT_DIR / "config.example.toml"
    with path.open("rb") as f:
        return tomllib.load(f)


def db_path_arg(doc: str) -> Path | None:
    """Return the .rmtree path from argv[1], or print usage/error and return None."""
    if len(sys.argv) < 2:
        print(doc)
        return None
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"File not found: {path}")
        return None
    return path


@contextmanager
def output_file(name: str, folder: str = "general") -> Iterator[Path]:
    """Send stdout to tmp/output/<folder>/<YYYYMMDD_HHMMSS>_<name>.txt, then print its path.

    folder groups output by piece of work: "general" for checks and listings,
    "birth_register" for the birth index work.
    """
    directory = OUTPUT_DIR / folder
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{datetime.now():%Y%m%d_%H%M%S}_{name}.txt"
    with path.open("w", encoding="utf-8") as f, redirect_stdout(f):
        yield path
    print(f"Output written to: {path}")
