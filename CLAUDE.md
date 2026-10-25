# RootsMagic scripts

## Aim

Python scripts to inspect, and later change, a RootsMagic 12 family tree file
(`.rmtree`, an SQLite database). First goal: read-only checks of the database
contents. Later goal: scripted changes such as linking scan files (PDF, TIF) to
citations.

## Structure

Scripts are grouped in folders under `scripts/` by what they work on. Every
script that writes is a dry run unless given `--apply`.

| Path | Contents |
|---|---|
| `scripts/rmutils.py` | Shared helpers: RMNOCASE stand-in, connections, output file, Fields XML, dates and SortDate, Windows files (list, dates, rename, move, copy, hash), RootsMagic running |
| **`scripts/general/`** | **Read-only checks and listings** |
| `schema.py` | Tables, columns, indexes, row counts, views, triggers |
| `people.py` | Everyone in the tree: ID, sex code, primary name, birth/death year |
| `check.py` | Issue checks; one `@check` function per issue (includes unused places and near-identical place details) |
| `find_person.py` | Finds people by surname and the start of given names, including alternative names |
| `missing_records.py` | Checklists of records still to find (birth, marriage, death indexes, censuses, 1939 Register) for the root person's family by degree of separation, one `notes/missing/missing_*.md` file per record type |
| `working_copy.py` | `fetch` the test tree as the working copy, `push` it back (refused if RootsMagic saved the test tree since), `status`; checks RootsMagic is closed and compares hashes |
| **`scripts/births/`** | **Birth index (register) work** |
| `freebmd_births.py` | FreeBMD birth index source and citations to template 6 |
| `gro_index_citation.py` | Adds a GRO online index citation (source "Birth Register - UK - GRO") to a Birth event |
| `move_citations_to_birth.py` | Moves citation links from register events to the Birth event (`--register-fact`; `--fact 2` Death, `--source`) |
| `remove_register_events.py` | Deletes register events, first copying their place to a Birth event with none (`--fact 2` Death; `--convert` where the person has none) |
| `birth_dates_before.py` | Quarter-only Birth dates to "before" the month after the quarter (`--fact 2` Death) |
| `birth_index_media.py` | Fills Caption, RefNumber, Description and Date of birth index scans |
| `birth_index_media_dates.py` | Sets birth index scan dates to the plain registration quarter |
| **`scripts/deaths/`** | **Death index (register) work** |
| `freebmd_deaths.py` | FreeBMD death index source and citations to template 6; merges per-person duplicates |
| `death_index_media.py` | Fills Caption, RefNumber, Description and Date of death index scans (FreeBMD and Ancestry) |
| `freebmd_death_citation.py` | Adds a FreeBMD death index citation to a Death event |
| `ancestry_deaths.py` | Ancestry death index source and citations to template 6; merges per-person duplicates |
| **`scripts/marriages/`** | **Marriage index (register) work** |
| `freebmd_marriages.py` | FreeBMD marriage index: one citation per partner's entry, with its scan, on the couple's Marriage |
| **`scripts/citations/`** | **Citations** |
| `change_citation_source.py` | Moves a citation to another source with new entry text and transcription |
| `correct_entry_page.py` | Corrects an index entry's page in a citation and its scans |
| `fix_name_stops.py` | Removes stray full stops after whole names in index entries |
| `merge_duplicate_citations.py` | Merges citations of the same entry cited twice on one record |
| `resolve_possible_entries.py` | Keeps one of two possible index citations, deletes the other |
| `set_citation_note.py` | Sets citation notes (Comments) |
| `set_citation_quality.py` | Sets the quality of unassessed citation links (`--fact`, `--item` filters) |
| `link_citations_to_fact.py` | Links a source's citations to another fact (e.g. Birth) of the same person |
| `link_citation.py` | Links one citation to one event, with a quality (for citations on more than one person) |
| `set_citation_text.py` | Sets transcriptions (ActualText) where there are none |
| `add_citation.py` | Adds a citation to an existing source (template citation fields or free-form Page) and links it to events, families or names |
| `footnote_preview.py` | Prints a citation's footnote, short footnote and bibliography from its template (approximate) |
| **`scripts/sources/`** | **Sources** |
| `delete_source.py` | Deletes a source with no citations or attachments |
| `rename_source.py` | Renames a source |
| `set_source_text.py` | Sets a source's text (description of the source); `--note` sets its note (Comments) |
| `source_inventory.py` | Lists a source with its citations, their links (fact, owner, date, place), quality and scans (read-only) |
| `source_people.py` | Lists the people a source's citations touch, with Birth/Christen/Death, parents and marriages (read-only) |
| `split_source.py` | Moves matching citations to another source, existing or new |
| **`scripts/media/`** | **Media** |
| `attach_scan.py` | Attaches a scan file to a citation, with thumbnail and access date |
| `rename_scan.py` | Renames a scan file, or moves it to another folder, on the drive and in the media rows that use it |
| `file_input_scan.py` | Moves a new record file from the input folder to its record type's folder under a new name; shows its access date and files of the same base name |
| `list_scans.py` | Lists a Records folder with file dates (G16 access dates), skipping `unsure` and `Unsorted`; `--tree` shows the media rows using each file |
| **`scripts/people/`** | **People** |
| `rename_person.py` | Changes a person's primary given names and/or surname |
| `add_alternative_name.py` | Adds an alternative (AKA) name to a person, cited to a citation |
| `set_event_date.py` | Sets an event's encoded date and its SortDate |
| `set_event_place.py` | Sets an event's place and place detail |
| `set_event_note.py` | Sets an event's note, replacing what it holds |
| **`scripts/places/`** | **Places** |
| `rename_place.py` | Renames a place or place detail (and its sort name) |
| `merge_places.py` | Moves every fact from one place or detail to another, then deletes the emptied one |
| `delete_place.py` | Deletes a place or detail that nothing uses |
| **`scripts/tasks/`** | **RootsMagic tasks** |
| `create_task.py` | Creates a task linked to a person, as RootsMagic 12 stores one |
| `config.example.toml` | Settings (scan folder, input folder, skipped folders, age limits, test tree and working copy paths); copy to git-ignored `config.toml` |
| `tests/` | `unittest` tests; `support.py` builds a small fixture database |
| `.claude/skills/rm-schema/` | Skill that runs `schema.py` |
| `.claude/skills/rm-check/` | Skill that runs `check.py` |
| `.claude/skills/rm-missing-records/` | Skill that runs `missing_records.py` for a given degree of separation |
| `.claude/skills/rm-add-record/` | Skill that adds a found record (file in the input folder plus transcription) to the tree |
| `mise.toml` | Python version and uv; puts `scripts/` on `PYTHONPATH` so scripts in subfolders can import `rmutils`; activates `.venv` |
| `pyproject.toml`, `uv.lock` | Project dependencies, managed with uv, installed into the git-ignored `.venv` (PyMuPDF: renders part of a scan PDF enlarged, to read handwriting) |
| `tmp/output/` | Script output (git-ignored): `general/` for checks and listings, `birth_register/` for the birth index work, `death_register/` for the death index work |
| `notes/one_off/` | Applied one-off scripts that hold real names (Ancestry and FamilySearch birth index changes), kept out of git |
| `notes/issues/` | Issues notes per record type (`<type>_issues.md`: decisions, progress, issues; e.g. birth register IDs BR-n), with real names (git-ignored); open ones are also RootsMagic tasks |
| `notes/missing/` | Missing-record checklists (`missing_*.md`) written by `missing_records.py` |

Tree files (`*.rmtree`) are git-ignored. `Morton Tree.rmtree` in the project
root is an old, unchanged copy of the live tree (2026-10-14); it has none of the
changes made since. Scripts and checks use the working copy
`tmp/work/Morton Tree.rmtree`, fetched from the test tree (see below).

## Commands

- Run a script: `mise exec -- python scripts/<folder>/<name>.py "<path.rmtree>" [args]`
- Run tests: `mise exec -- python -m unittest discover -s tests -v`
- Install dependencies (new clone, or after `uv.lock` changes): `mise install`, then `mise exec -- uv sync`
- Add a dependency: `mise exec -- uv add <package>`, then pin it with `==` in `pyproject.toml`
- uv's version is pinned in both `mise.toml` and `pyproject.toml` (`[tool.uv] required-version`); change both together

## Conventions

- Scripts take the `.rmtree` path as the first argument and open it read-only
  via `rmutils.connect_readonly`.
- Scripts with large output write it through `rmutils.output_file(name)` to
  `tmp/output/<folder>/<YYYYMMDD_HHMMSS>_<name>.txt` (underscores only) and print
  the path. The folder is "general" by default; each piece of work gets its own
  folder (e.g. "birth_register").
- Put shared code in `rmutils.py`.
- Useful helper scripts (e.g. read-only listings used more than once) go in the repo under
  `scripts/` with a test, not in a temporary scratch folder (user's rule, 2026-10-20).
- Tests cover each script's `main()` only, not private functions. They use a
  fixture database in a temp folder, redirect `OUTPUT_DIR`, and freeze the clock.
- No real family data in committed files: tests use invented names, and
  scripts take people, citations and entries as arguments rather than
  hard-coding them. The repository is public. A script that has to hold real
  values goes in the git-ignored `notes/one_off/`. Search the files before every
  commit.

## Safety rules

- Never work on the live tree file. Work on a copy, and check a backup exists.
- RootsMagic must be closed while a script touches the file.
- Read-only first: inspect the schema and existing rows before writing.
- Every write script needs a dry-run mode that lists the proposed changes, and
  runs in a transaction so it rolls back on error. Check the dry run and continue
  to the writing step if there were no issues. If there were issues then report
  and wait for further instructions.
- After changes, the user opens the copy in RootsMagic, runs its database tools
  (including rebuild indexes), and checks results before replacing the real file.

## Working files and backups

| File | Role |
|---|---|
| `H:\My Drive\RootsMagic\RootsMagic8\Morton Tree.rmtree` | Live tree. Not touched until a record type is finished. |
| `H:\My Drive\RootsMagic Work\Morton Tree - FreeBMD template test.rmtree` | Test tree. All changes accumulate here, record type by record type; the user checks it in RootsMagic. |
| `tmp/work/Morton Tree.rmtree` | Working copy: where scripts write, and the file for read-only checks. Start each change from the latest test tree (`scripts/general/working_copy.py fetch`), apply, then copy back over the test tree (`working_copy.py push`). The script copies through PowerShell, since WSL cannot see H:, checks RootsMagic is closed and compares hashes. |

- The working copy may be deleted between sessions; fetch it again from the
  test tree before use. The skills ask which file to use when no path is given.
- The test tree replaces the live tree only when the user says so, after a
  record type is finished. At that point: keep the old live tree as a dated
  backup beside it, copy the test tree over it, and read it back to confirm.
- The test tree may hold changes RootsMagic made on save (e.g. tabs in
  ActualText replaced with spaces); always start from it.

## Database notes (verify against the file; do not assume)

- RMNOCASE is a RootsMagic collation. Register a case-insensitive stand-in
  before querying (done in `connect_readonly`). Writes touching RMNOCASE
  indexes need RootsMagic's rebuild-indexes afterwards.
- The stand-in sorts some names differently from RootsMagic (punctuation,
  digits, mixed case, e.g. "St John's", "Nord-Pas-de-Calais"). So
  `PRAGMA integrity_check` run from Python reports rows "missing from index"
  for RMNOCASE indexes even after RootsMagic rebuilds them. Use RootsMagic's
  Test database integrity instead (seen 2026-10-15).
- Links use an owner-type code plus an owner ID (e.g. `MediaLinkTable`,
  `CitationLinkTable`). Find the codes from links the user made by hand; do not guess.
  Confirmed from this file's data: MediaLinkTable 0 person, 2 event, 3 source,
  4 citation; CitationLinkTable 0 person, 1 family, 2 event, 7 name (NameID);
  NameTable NameType 1 AKA (both from an alternative name made by hand); WitnessTable
  (shared event) EventID, PersonID, WitnessOrder, Role (RoleTable; 39 = Witness on Marriage),
  made by hand 2026-10-18; EventTable 0 person,
  1 family; MediaType 1 image, 2 file. Fact types 1 Birth, 2 Death, 3 Christen;
  custom (record) facts are 1000+.
- Scans live in `H:\My Drive\Records` (Google Drive). WSL cannot see H:, so list
  files with `powershell.exe` (`rmutils.list_windows_files`).
- Dates are in RootsMagic's own encoded text format, e.g. `D.+18870317..+00000000..`
  (characters 4-11 are YYYYMMDD; `.` alone means no date). Confirmed by how
  RootsMagic 12 displays them (2026-10-15): `D-` is a range ("April 1886–June
  1886"), `DR` is "between ... and ...", and `A` at character 13 adds "about" to
  the first date. `DB+18860400..+00000000..` is "Bef Apr 1886" (written by
  RootsMagic); `DA+19121230..+00000000..` is "Aft 30 Dec 1912" (made by hand,
  2026-10-22). `DS+...` is not confirmed. Copy the pattern from existing rows.
- SortDate: `rmutils.sort_date(date)` gives it for single, "before", range and
  "between" dates; it matches every such date in the tree (fitted from the
  data, not documented), and the one "after" date made by hand. It returns None for dates with no year, double-dated
  years and `DS` dates.
- User's choice for births known only from the registration quarter: "before"
  the month after the quarter (Jan-Mar 1886 -> Bef Apr 1886).
- Source and citation template values are XML in the `Fields` BLOB:
  `<Root><Fields><Field><Name>..</Name><Value>..</Value></Field>..</Fields></Root>`.
  Older source rows add a byte-order mark, XML declaration and trailing newline;
  RootsMagic 12 saves source rows without them (seen 2026-10-15). Citation rows
  have neither. Saving a citation in RootsMagic 12 replaced tabs in its
  ActualText with spaces. `CitationName` is the citation field values joined with
  "; " in template order. `UTCModDate` is days since 1899-12-30, UTC.
  Helpers: `rmutils.read_fields`, `fields_blob`, `utc_mod_date`.
- `CitationLinkTable.Quality` is three characters (RootsMagic 12, set by hand
  2026-10-15): information P/S/~, evidence D/I/N/~, source O/X/~ (X derivative).
  User's rating for GRO index entries on Birth events: `PIX` (primary,
  indirect, derivative). `~~~` means not assessed.
- Tasks (TaskTable, TaskLinkTable): RootsMagic 12 writes TaskType 0, Status 0,
  Priority 4 (default); "Low" priority is 6 (set by hand, 2026-10-15). Task
  links to a person use OwnerType 0. Open data issues are recorded as tasks
  linked to the person, with a note on the affected citations pointing to the task.
- `MultimediaTable` stores folder (`MediaPath`) and file name (`MediaFile`)
  separately. Check existing rows (including relative paths) before changing paths.
- Thumbnails are only made for media type "Image"; PDFs work better as "File".
- Media details convention (user's choice, 2026-10-15): Caption
  "Surname, Given – record type – YYYY Qn" (the Media page sorts by caption);
  RefNumber the official reference (GRO: "YYYY Qn District Volume Page");
  Description the entry's transcription, then where the image came from;
  Date copied with SortDate from the event the citation supports.
- Scans are attached to citations, not sources.
- New or completed FreeBMD citations get the FreeBMD citation link
  (`https://www.freebmd.org.uk/cgi/information.pl?cite=...&scan=1`) as the last
  line of the transcription, as in existing ones (user's request, 2026-10-15).
  FreeBMD blocks automated access, so the user supplies the link.
- GRO online index checks (user's choice, 2026-10-15): recorded as their own
  citation under "Birth Register - UK - GRO", with the saved search result PDF
  (Births\Britain\GRO Searches) attached; the FreeBMD citation's note points to it.
- Scan folders are organised by record type; files are named by person and
  date. Ask for real examples before writing any file-name parsing.
- Reference: sqlitetoolsforrootsmagic.com (community; may describe older versions).

## Working with the user

- UK, own family history. Keep explanations short; define terms and acronyms.
- Answer the question first.
- Simple shell commands only: one command per call, no chaining or pipes.
- Code runs in WSL; RootsMagic stores Windows paths (`C:\...`), seen here as `/mnt/c/...`.
