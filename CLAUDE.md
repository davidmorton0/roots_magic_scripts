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
| `find_person.py` | Finds people by surname and the start of given names, including alternative names |
| `missing_records.py` | Checklists of records still to find (birth, marriage, death indexes, censuses, 1939 Register) for the root person's family by degree of separation, one `notes/missing/missing_*.md` file per record type |
| `working_copy.py` | `fetch` the test tree as the working copy, `push` it back (refused if RootsMagic saved the test tree since), `status`; checks RootsMagic is closed and compares hashes |
| **`scripts/citations/`** | **Citations** |
| `merge_duplicate_citations.py` | Merges citations of the same entry cited twice on one record |
| `evaluate_links.py` | Flags citation links missing or not allowed for the record type (`.claude/skills/rm-evaluate-links/facts_cited.md`); names the event to link or the fact to create (read-only) |
| `evaluate_quality.py` | Flags unrated link qualities and ratings that differ from `.claude/skills/rm-evaluate-quality/quality.md` (read-only) |
| `evaluate_citation.py` | Fetches citations (by source, citation or all) and flags what does not fit the citation standards and forms in `.claude/skills/rm-evaluate-source/source_types.md` (read-only) |
| `footnote_preview.py` | Prints a citation's footnote, short footnote and bibliography from its template (approximate) |
| **`scripts/sources/`** | **Sources** |
| `evaluate_source.py` | Fetches sources and flags what does not fit the source standards and source-type table in `.claude/skills/rm-evaluate-source/source_types.md` (read-only) |
| `source_inventory.py` | Lists a source with its citations, their links (fact, owner, date, place), quality and scans (read-only) |
| `source_people.py` | Lists the people a source's citations touch, with Birth/Christen/Death, parents and marriages (read-only) |
| `split_source.py` | Moves matching citations to another source, existing or new |
| **`scripts/media/`** | **Media** |
| `evaluate_scans.py` | Flags scan captions, reference numbers, descriptions, dates, file names, folders, media types and shared rows against `.claude/skills/rm-evaluate-scans/scan_forms.md` (read-only) |
| `list_scans.py` | Lists a Records folder with file dates (G16 access dates), skipping `unsure` and `Unsorted`; `--tree` shows the media rows using each file |
| **`scripts/people/`** | **People** |
| `evaluate_record_events.py` | Says for each record event (fact 1000+) whether it is ready to delete, what to copy to its main fact first, or that it must be converted (`.claude/skills/rm-remove-record-events/record_facts.md`; read-only) |
| **`scripts/places/`** | **Places** |
| `merge_places.py` | Moves every fact from one place or detail to another, then deletes the emptied one |
| `evaluate_places.py` | Flags G21 problems: addresses in descriptions or held as places, details not under their place, the same detail twice (read-only) |
| **`scripts/records/`** | **Generic `get`, `create`, `edit`, `delete` sub-commands per record type (dry run unless `--apply`; refuses to delete what is still used). Person, event, family and child create defaults come from the one-off scripts and match the rows in the tree, but are not yet checked against rows made by hand** |
| `citation.py` | Citations: template fields (CitationName rebuilt), notes, text, links on create |
| `citation_link.py` | Citation links to a person, family, event or name, with quality |
| `source.py` | Sources: template source fields, text, note, name |
| `media.py` | Media rows and their links to a person, event, source or citation; `get --path` finds the rows using one file. Does not touch the file itself (see `scripts/files/`) |
| `person.py` | People, with the primary name |
| `name.py` | Alternative names |
| `event.py` | Events (facts) of a person or family: type, date and SortDate, place, detail |
| `family.py` | Families and children; keeps each person's SpouseID and ParentID right |
| `place.py` | Places and place details (sort name follows the name) |
| `task.py` | Tasks and their links to people |
| **`scripts/files/`** | **File operations on the Windows drive, no database** |
| `file.py` | `list` (files and dates; `--skip` leaves out skipped and Unsorted folders), `info` (date, SHA-256), `rename`, `move`, `copy` (hashes compared); dry run unless `--apply` |
| **`scripts/validate/`** | **Read-only validation, one script per record type (`validate_<type>.py`); output in `tmp/output/validate/`** |
| `validate_common.py` | Shared: tree loading, check registry, runner, date form and SortDate checks |
| `validate_source.py` | Unused sources |
| `validate_citation.py` | Citations with no scan, unused citations |
| `validate_citation_link.py` | Links to a missing citation or record (names included), quality not three valid characters |
| `validate_media.py` | Scan files and media rows (`--scan-list`, `--no-scans`), date form, SortDate |
| `validate_person.py` | Name, sex code, events, birth, connections, primary events, birth after death, ParentID and SpouseID |
| `validate_name.py` | Missing person, blank parts, spaces, case, duplicates, date form |
| `validate_event.py` | Citations, date, place, years against birth and death, missing owner, date form, SortDate, witnesses |
| `validate_family.py` | One partner, parent and marriage ages, missing partner, child rows |
| `validate_place.py` | Unused places, near-identical details |
| `validate_task.py` | Unlinked tasks, links to a missing task or person, date form |
| `config.example.toml` | Settings (scan folder, input folder, skipped folders, age limits, test tree and working copy paths); copy to git-ignored `config.toml` |
| `tests/` | `unittest` tests; `support.py` builds a small fixture database |
| `.claude/skills/rm-schema/` | Skill that runs `schema.py` |
| `.claude/skills/rm-check/` | Skill that runs the `scripts/validate/validate_*.py` scripts (all, or chosen record types) |
| `.claude/skills/rm-missing-records/` | Skill that runs `missing_records.py` for a given degree of separation |
| `.claude/skills/rm-add-record/` | Skill that adds a found record (file in the input folder plus transcription) to the tree |
| `.claude/skills/rm-evaluate-citation/`, `rm-evaluate-links/`, `rm-add-people/`, `rm-remove-record-events/`, `rm-evaluate-places/`, `rm-evaluate-scans/`, `rm-evaluate-quality/` | Sub-skills of rm-record-cleanup step 5, one per item: flag with the matching `evaluate_*.py`, decide, fix with `records/` and `files/`; each holds its table (drafts) |
| `.claude/skills/rm-evaluate-source/` | Skill that evaluates sources: `evaluate_source.py` flags, decisions, fixes with `records/source.py`; holds the source standards and source-type table (`source_types.md`) |
| `mise.toml` | Python version and uv; puts `scripts/` on `PYTHONPATH` so scripts in subfolders can import `rmutils`; activates `.venv` |
| `pyproject.toml`, `uv.lock` | Project dependencies, managed with uv, installed into the git-ignored `.venv` (PyMuPDF: renders part of a scan PDF enlarged, to read handwriting) |
| `tmp/output/` | Script output (git-ignored): `general/` for checks and listings, `validate/` for the validation scripts, `birth_register/` for the birth index work, `death_register/` for the death index work |
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
