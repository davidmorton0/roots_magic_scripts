"""Print a citation's footnote, short footnote and bibliography (read-only, approximate).

Fills the source template's sentences (SourceTemplateTable Footnote, ShortFootnote,
Bibliography) with the source's and citation's Fields values. The template language is
not documented by RootsMagic; these rules follow the templates in this tree:
  [Field]          the field's value
  [Field:Mod]      Surname: last word; Reverse: "Surname, Given"; Caps: first letter
                   upper-case; Year: the four-digit year; others (Abbrev...): the value
  <...>            printed only when every field inside has a value
  <?[F]|yes|no>    "yes" when F has a value, else "no"
  <i>...</i>       italics, shown as *...*
Free-form sources (template 0): the source's Footnote, ShortFootnote and Bibliography
fields, with the citation's Page added to both footnotes after a comma.
RootsMagic's own output is the authority; check it there.

Usage: python footnote_preview.py PATH_TO_RMTREE CITATION_ID
"""

import re
import sys

from rmutils import connect_readonly, db_path_arg, read_fields

FIELD = re.compile(r"\[([^\]:]+)(?::([^\]]+))?\]")


def modify(value: str, mod: str | None) -> str:
    if not value or not mod:
        return value
    words = value.split()
    if mod == "Surname":
        return words[-1]
    if mod == "Reverse":
        return f"{words[-1]}, {' '.join(words[:-1])}" if len(words) > 1 else value
    if mod == "Caps":
        return value[0].upper() + value[1:]
    if mod == "Year":
        found = re.search(r"\b(\d{4})\b", value)
        return found.group(1) if found else value
    return value


def closing(text: str, start: int) -> int:
    """Index of the '>' closing the '<' at start (nested groups; <i> and </i> skipped)."""
    depth, i = 0, start
    while i < len(text):
        if text.startswith(("<i>", "</i>"), i):
            i += 3 if text.startswith("<i>", i) else 4
            continue
        if text[i] == "<":
            depth += 1
        elif text[i] == ">":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError(f"unclosed '<' at {start}")


def split_top(text: str, sep: str = "|") -> list[str]:
    parts, depth, current = [], 0, ""
    for ch in text:
        depth += ch == "<"
        depth -= ch == ">"
        if ch == sep and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    return parts + [current]


def render(text: str, values: dict[str, str]) -> tuple[str, bool]:
    """(rendered text, True if every field met had a value)."""
    out, complete, i = "", True, 0
    while i < len(text):
        if text.startswith("<i>", i):
            out, i = out + "*", i + 3
        elif text.startswith("</i>", i):
            out, i = out + "*", i + 4
        elif text[i] == "<":
            end = closing(text, i)
            inner = text[i + 1:end]
            if inner.startswith("?"):
                test, *branches = split_top(inner[1:])
                has = bool(render(test, values)[0].strip()) and render(test, values)[1]
                branch = branches[0] if has else (branches[1] if len(branches) > 1 else "")
                out += render(branch, values)[0]
            else:
                part, ok = render(inner, values)
                out += part if ok else ""
            i = end + 1
        elif text[i] == "[":
            m = FIELD.match(text, i)
            if not m:
                out, i = out + text[i], i + 1
                continue
            value = modify(values.get(m.group(1), ""), m.group(2))
            complete = complete and bool(value)
            out, i = out + value, m.end()
        else:
            out, i = out + text[i], i + 1
    return out, complete


def main() -> int:
    path = db_path_arg(__doc__)
    if path is None:
        return 2
    if len(sys.argv) < 3 or not sys.argv[2].isdigit():
        print(__doc__.strip().splitlines()[-1])
        return 2
    cid = int(sys.argv[2])
    conn = connect_readonly(path)
    try:
        row = conn.execute("SELECT s.TemplateID, s.Fields, c.Fields FROM CitationTable c JOIN SourceTable s"
                           " ON s.SourceID = c.SourceID WHERE c.CitationID = ?", (cid,)).fetchone()
        if row is None:
            print(f"No citation C{cid}")
            return 1
        template, source_fields, citation_fields = row
        values = {**read_fields(source_fields), **read_fields(citation_fields)}
        if template == 0:
            page = values.get("Page", "")
            add = f", {page}" if page else ""
            sentences = (values.get("Footnote", "") + add, values.get("ShortFootnote", "") + add,
                         values.get("Bibliography", ""))
        else:
            sentences = conn.execute("SELECT Footnote, ShortFootnote, Bibliography FROM SourceTemplateTable"
                                     " WHERE TemplateID = ?", (template,)).fetchone()
            if sentences is None:
                print(f"No template {template} for C{cid}")
                return 1
            sentences = tuple(render(s or "", values)[0] for s in sentences)
    finally:
        conn.close()
    print(f"C{cid} (template {template}; approximate, check in RootsMagic)")
    for label, text in zip(("Footnote", "Short footnote", "Bibliography"), sentences):
        print(f"{label}: {re.sub(r' {2,}', ' ', text).strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
