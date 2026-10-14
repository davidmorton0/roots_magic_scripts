# RootsMagic scripts

## Aim

Python scripts to inspect, and later change, a RootsMagic 12 family tree file
(`.rmtree`, an SQLite database). First goal: read-only checks of the database
contents. Later goal: scripted changes such as linking scan files (PDF, TIF) to
citations.

## Structure

| Path | Contents |
|---|---|
| `scripts/rmutils.py` | Shared helpers: RMNOCASE stand-in, read-only connection, output file |
| `scripts/schema.py` | Tables, columns, indexes, row counts, views, triggers |
| `scripts/people.py` | Everyone in the tree: ID, sex code, primary name, birth/death year |
| `tests/` | `unittest` tests; `support.py` builds a small fixture database |
| `.claude/skills/rm-schema/` | Skill that runs `schema.py` |
| `mise.toml` | Python version |
| `tmp/output/` | Script output (git-ignored) |

The tree file (`*.rmtree`) sits in the project root and is git-ignored.

## Commands

- Run a script: `mise exec -- python scripts/<name>.py "<path.rmtree>" [args]`
- Run tests: `mise exec -- python -m unittest discover -s tests -v`

## Conventions

- Scripts take the `.rmtree` path as the first argument and open it read-only
  via `rmutils.connect_readonly`.
- Scripts with large output write it through `rmutils.output_file(name)` to
  `tmp/output/<YYYYMMDD_HHMMSS>_<name>.txt` (underscores only) and print the path.
- Put shared code in `rmutils.py`.
- Tests cover each script's `main()` only, not private functions. They use a
  fixture database in a temp folder, redirect `OUTPUT_DIR`, and freeze the clock.
- No real family data in committed files (tests use invented names).

## Safety rules

- Never work on the live tree file. Work on a copy, and check a backup exists.
- RootsMagic must be closed while a script touches the file.
- Read-only first: inspect the schema and existing rows before writing.
- Every write script needs a dry-run mode that lists the proposed changes, and
  runs in a transaction so it rolls back on error. Show the dry run and wait for
  approval before writing.
- After changes, the user opens the copy in RootsMagic, runs its database tools
  (including rebuild indexes), and checks results before replacing the real file.

## Database notes (verify against the file; do not assume)

- RMNOCASE is a RootsMagic collation. Register a case-insensitive stand-in
  before querying (done in `connect_readonly`). Writes touching RMNOCASE
  indexes need RootsMagic's rebuild-indexes afterwards.
- Links use an owner-type code plus an owner ID (e.g. `MediaLinkTable`,
  `CitationLinkTable`). Find the codes from links the user made by hand; do not guess.
- Dates are in RootsMagic's own encoded text format. Copy the pattern from
  existing rows; do not write dates until the format is confirmed.
- `MultimediaTable` stores folder (`MediaPath`) and file name (`MediaFile`)
  separately. Check existing rows (including relative paths) before changing paths.
- Thumbnails are only made for media type "Image"; PDFs work better as "File".
- Scans are attached to citations, not sources.
- Scan folders are organised by record type; files are named by person and
  date. Ask for real examples before writing any file-name parsing.
- Reference: sqlitetoolsforrootsmagic.com (community; may describe older versions).

## Working with the user

- UK, own family history. Keep explanations short; define terms and acronyms.
- Answer the question first.
- Simple shell commands only: one command per call, no chaining or pipes.
- Code runs in WSL; RootsMagic stores Windows paths (`C:\...`), seen here as `/mnt/c/...`.
