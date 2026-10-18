---
name: rm-record-cleanup
description: Clean up one record type in the RootsMagic tree (e.g. marriage registers, death certificates), following the steps used for UK birth registers and birth certificates - inventory, scope, sources, citations, links to facts, people and places, scans, quality, issues - with all questions asked up front, then every change made without further confirmation, and issues left to the end.
argument-hint: "<record type, e.g. 'UK marriage registers'>"
---

Clean up one record type: $ARGUMENTS

Follow CLAUDE.md throughout (safety rules, working files, database notes,
conventions). Apply the standing decisions in `source_standards.md` (this folder)
without asking; add new standing decisions there. This file lists the steps and the specific actions used for UK
birth registers (indexes) and birth certificates (2026-10).

The work runs one source at a time (user's choice, 2026-10-16). For each source, in
three phases:

1. **Questions up front.** Steps 0-4 are read-only. Collect every question the changes
   depend on (scope, records the user must read, decisions) and ask them all before any
   change, one at a time, each with labelled options and what each option does. Record each
   answer under "Decisions" in `notes/<type>_issues.md` as it is given.
2. **Changes without further confirmation.** The answers are the approval. Run step 5 from
   start to finish without stopping to ask: each change still has a dry run, checked against
   the decisions, then is applied, read back and copied over the test tree.
3. **Issues at the end.** Anything found during the changes that the decisions do not cover
   is not asked about then: leave those records unchanged, note them under "Issues" in
   `notes/<type>_issues.md`, and carry on. When everything else is done, present the issues
   for the user to resolve, one at a time.

## 0. Working copy

1. Check RootsMagic is closed: `powershell.exe -NoProfile -Command 'Get-Process *RootsMagic* -ErrorAction SilentlyContinue'`.
2. Fetch the test tree: PowerShell `Copy-Item` to `$env:TEMP\h-test-copy.rmtree`, then `cp` from
   `/mnt/c/Users/<user>/AppData/Local/Temp/` to `tmp/work/`. Note its hash (`Get-FileHash`).
3. Before every apply, compare the test tree's hash with the last copy. If it changed (RootsMagic
   saved it), stop and tell the user: the test tree was changed outside this work.

## 1. Inventory (read-only)

1. Sources for the type: name, template, citation count, source fields, source text
   (look for notes copied from other sites).
2. Record facts (FactTypeID 1000+, e.g. "Marriage Register - UK") and how many events use them.
3. For each citation: what it links to (CitationLinkTable owner type, event type, person), fields,
   CitationName, transcription (ActualText), note (Comments), quality, scans (MediaLinkTable 4).
4. Duplicates: one record cited by several citations (one per fact or person it was linked to).
5. The people: their main fact for this type (Birth/Marriage/Death) and its existing citations,
   the related family (FamilyTable), parents (ChildTable), and other facts in the same years.
6. Scans on disk in the type's folder under `H:\My Drive\Records` (list with PowerShell);
   compare with the media rows. Copy the scans to `tmp/work/` and read them.
7. Report the inventory as short tables. Real names stay out of committed files.

## 2. Scope (user decides)

- Which sources and countries. Records left out are not listed anywhere as "out of scope".
- Records without scans: the user may hold paper copies. If asked, set the citation note
  "No scan; paper copy held." (`scripts/citations/set_citation_note.py`).
- Issues the user hands to RootsMagic tasks are out of scope for the clean-up.

## 3. Read every record

Records the user has to read (missing or unreadable transcriptions) are questions for phase 1:
give the person and the full scan path for each. Entries that only look wrong (they disagree
with the tree) do not block a change: list them as issues for the end.

A record read from its scan is checked against the tree (index: age against the birth year,
district against the death or birth place, quarter against the event date). A reading that
fits is used without asking; only one that does not fit goes to the user.


- Transcribe each scan in the layout of existing transcriptions ("Key: value" lines, `\r\n`).
- Check every reference against the image. Certificates: the certificate number is the
  printed serial (e.g. "BXCB 123456"); the "Application Number" is not it.
- Note what the record states for each person (dates, places, addresses, occupations,
  relationships, informant). Uncertain handwriting is a point to check.

## 4. Decisions (ask, with options; all before step 5)

Work out every decision the changes in step 5 will need for the current source, and ask them
all now. Before asking anything, check the decisions already made for this type. If one
covers the case, apply it and name it; do not ask again. Write each decision down as it is made, in its
exact wording (e.g. "Birth: `SIX` before 1969, `SDX` from 1969"), under "Decisions" in
`notes/<type>_issues.md`, and code from that wording, not from a pattern standing in for it.

1. Links: usual practice is to cite the record on each fact it supports, not on a record event.
   Facts by type (confirm with the user):

   | Type | Facts to cite |
   |---|---|
   | Birth index | child's Birth |
   | Birth certificate | child's Birth; father's Occupation; Residence of both parents; parents' family |
   | Marriage index | the couple's Marriage (family event) |
   | Marriage certificate | Marriage; each spouse's Occupation and Residence; each father's Occupation; witnesses |
   | Death index | Death |
   | Death certificate | Death; Occupation; informant's Residence |

2. Dates of new facts: the record's event date or its registration date (birth certificates:
   registration date). Index-only dates: "before" the month after the quarter (births).
3. Residence: the informant only, or both parents/spouses (births: both parents).
4. People named on the record but not in the tree: add them or not (births: added).
5. Addresses: as place details (PlaceType 2) under the event's place; reuse an existing detail;
   if the same address exists twice, move the events to the chosen one and delete the other.
6. Family citation (CitationLinkTable owner type 1): shows next to the spouse details on both
   partners and next to the parents on every child.
7. Quality per link type (information P/S, evidence D/I/N, source O/X). Used so far:
   GRO index entry on Birth `PIX`; certificate on Birth, Occupation and informant's Residence
   `PDX`; other parent's Residence and family `PIX`. A GRO certificate is a copy of the GRO's
   copy of the register: derivative (X).
8. Source: name "<Record> - <Country> - <Provider>". Online indexes and databases: always
   template 6 (Complex Website) with AccessDate, SpecificItem, Citing; do not ask (user's
   standing choice, 2026-10-17). Certificates: free-form (template 0) to the
   Evidence Explained model; source Footnote and ShortFootnote "England, <type> certificate
   (certified copy)", Bibliography "England. Registrar General. <Type> Certificates. General
   Register Office, Southport."; citation Page "<name>, <event date>; registered <quarter>,
   <district> district, <sub-district> sub-district, entry <n>; certificate <number>, issued
   <date>, General Register Office, Southport". RootsMagic adds Page to both footnotes.

## 5. Changes (dry run, apply; no confirmation)

Every change: a script with a dry run, checked against the decisions, then applied in one
transaction to the working copy; then read back, copy over the test tree, compare hashes.
Do not stop to show dry runs or ask for approval; the reports stay in `tmp/output/<folder>/`.
Records a dry run cannot handle under the decisions are left unchanged and noted as issues.
A problem with the write itself (the dry run fails or refuses, or its counts do not match the
decisions after the script is corrected) stops the work: report it and wait (CLAUDE.md).
Generic scripts go in `scripts/<folder>/` with tests; scripts holding real values go in
`notes/one_off/`. Reuse existing scripts where they fit (`scripts/citations/`,
`scripts/sources/`, `scripts/media/`, `scripts/tasks/`).

After each apply, tick the step under "Progress" in `notes/<type>_issues.md` and add any new
issue straight away, so the work can be picked up if the session ends.

After each dry run, check its counts against every recorded decision. A record that a decision
covers but the script missed is a bug to fix before applying, not a new question.

1. Source: rename, template, fields (`rmutils.fields_blob`, no declaration), clear stray text.
2. Citations: keep one per record; delete duplicates with their citation and media links;
   correct fields; rebuild CitationName (template citation fields joined with "; ", or the Page
   text for free-form); add transcriptions; FreeBMD citations end with the FreeBMD link.
3. Links: add citation links to each supported fact (Quality `~~~` until rated).
4. New facts (Occupation 26, Residence 29, ...): Date in RootsMagic format, SortDate from
   `rmutils.sort_date`, PlaceID + SiteID, IsPrimary 1 if the person has no other fact of
   that type.
5. New people: PersonTable (UniqueID = 32 hex + checksum, Sex 0 male / 1 female, ParentID,
   SpouseID), NameTable (SortDate 9223372036854775807, SurnameMP/GivenMP = names),
   FamilyTable, ChildTable; set the child's ParentID. Copy the newest rows made in RootsMagic.
6. Record events: delete them and their citation links, after their date, place and notes
   are on the facts.
7. Places: put the address (place detail) on the main fact and new Residence facts.
8. Scans: one link to the kept citation; Caption "Surname, Given – <record type> – <date>",
   RefNumber the official reference (index: "YYYY Qn District Volume Page"; certificate: its
   number), Description the entry summary then where the image came from, Date and SortDate
   from the fact.
9. Quality: set per link type once agreed.
10. Open issues: a RootsMagic task linked to the person (`scripts/tasks/create_task.py`), a
    note on the affected citations, and a row in `notes/<type>_issues.md`.

## 6. Check and finish

1. After each apply, re-run the dry run (it should show nothing left to do) and check links,
   new rows and that no citation link points to a missing event or citation.
2. Report what was done (one short table per source), then the issues, one at a time.
3. The user opens the test tree in RootsMagic, runs rebuild indexes and test database
   integrity, and checks a footnote and the changed people.
4. `notes/<type>_issues.md`: sections Decisions, Progress, Issues, Handed to tasks, Not doing,
   Resolved.
5. `notes/checklist.md`: one line per record type; tick it only when the user says it is done.
6. Commit only when asked; search for real names before every commit; never push.
