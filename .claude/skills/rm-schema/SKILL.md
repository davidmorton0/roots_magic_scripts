---
name: rm-schema
description: Read the structure of the RootsMagic .rmtree database (tables, columns, indexes, row counts, views, triggers). Read-only. Use before writing any query or script against the tree file.
argument-hint: "[path-to-rmtree] [table ...]"
allowed-tools: Bash(mise exec -- python ${CLAUDE_PROJECT_DIR}/scripts/general/schema.py *)
---

Show the database structure. The script opens the file read-only and registers a
stand-in for RootsMagic's RMNOCASE collation (case-insensitive compare).

Arguments: $ARGUMENTS
- First argument: path to the .rmtree file. If none is given, ask which file to
  use (for example `tmp/work/Morton Tree.rmtree`, the working copy).
- Further arguments: table names to limit the output to (case-insensitive).

Run, from the project root:

```bash
mise exec -- python ${CLAUDE_PROJECT_DIR}/scripts/general/schema.py "<path>" [TABLE ...]
```

With no table names, the script writes the full report to
`tmp/output/general/<YYYYMMDD_HHMMSS>_schema.txt` and prints that path; read the file
from there. With table names, it prints the report directly.

Report the output as-is. Do not change the database.
