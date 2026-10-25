---
name: rm-add-record
description: Add one record the user has found (a scan file placed in the input folder, with its transcription) to the RootsMagic tree - identify the person, move and name the file in its record type's folder (renaming existing files of the same name where needed), create the citation under the standard source, link it to the facts it supports with their quality, attach the scan, then refresh the missing-record lists.
argument-hint: "<file name in the input folder> (transcription pasted in the message)"
---

Add a found record to the tree: $ARGUMENTS

Follow CLAUDE.md throughout (safety rules, working files, database notes, conventions) and the
standing decisions in `.claude/skills/rm-record-cleanup/source_standards.md` (G1-G39, facts per
record type, quality ratings). Apply them without asking; ask only what they do not cover.

## Inputs

- File name: a file in the input folder, `input_folder` in `config.toml`
  (`H:\My Drive\Records\Input`). The folder is skipped by the scan checks (`not_scan_folders`).
- Transcription: pasted by the user. Work from it; open the image only when the transcription
  lacks something the citation needs (a reference, an age, an address). Read it once (user's rule,
  2026-10-23).
- If the file or the transcription is missing, ask for it.

## Steps

1. **Working copy.** `scripts/general/working_copy.py fetch` (checks RootsMagic is closed).
2. **Record type and people.** From the transcription: the record type, the reference (quarter,
   district, volume, page; piece, folio, schedule; etc.) and every person on it. Find them in the
   tree with `scripts/general/find_person.py`, and check them against the tree (ages, dates,
   places, relationships; G15). Match the record to its item in the `notes/missing/missing_*.md` lists
   where there is one. If the record fits no one, or more than one person, ask (one question,
   labelled options, G36 wording: "Is <record> correct for <person>?").
3. **Same record already in the tree (G12).** Look for a citation of the same entry: the same
   household (census), the same index entry, or the same certificate. If there is one, the file
   becomes another scan of that citation, and the transcription and access date come from the
   newest copy (G12). Otherwise a new citation is made (step 6).
4. **Folder and file name.** Use the table below (taken from the scans already in the tree; check
   it against the existing files of that source if unsure). Name the file
   `<SUR>-<initials>-<code>-<year>[-Q<n>]` with the first three letters of the surname in capitals
   and the given-name initials, as the existing files are named (couples and households:
   `SUR.I-SUR.I-...`), the extension unchanged.
5. **Files of the same name.** Dry run `scripts/media/file_input_scan.py "<file>" "<target>"`: it
   prints the access date (the file's last-modified date, read before the move, G16) and the files
   in the target folder with the same base name.
   - Same base name, another record (another person or entry): the existing file is renamed with
     `-R1` (`scripts/media/rename_scan.py`, which renames it on the drive and in the media rows),
     and the new file takes the next free number (`-R2`, `-R3`; if `-R` numbers exist already,
     the next one).
   - The same record (same image; compare with `rmutils.windows_file_hash`): do not add the
     duplicate; report it and leave it in the input folder.
   - Several pages of one record: `-P1`, `-P2` (1921 census: `-1`, `-2`, as existing).
   Then move it: `file_input_scan.py ... --apply`.
6. **Citation.** `scripts/citations/add_citation.py` under the record type's source (table), with
   the source's template fields: template 6 AccessDate (from step 5, e.g. "3 June 2021"),
   SpecificItem and Citing in the form of that source's existing citations (copy one); free-form
   sources Page (G1, G20, G24). Transcription in the layout of the existing ones (G10, "Key: value"
   lines). FreeBMD citations end with the FreeBMD citation link (CLAUDE.md), which the user
   supplies. Ready-made scripts where they fit: `scripts/births/gro_index_citation.py` (GRO birth
   index), `scripts/deaths/freebmd_death_citation.py` (FreeBMD death index).
7. **Links and facts.** Link the citation to each fact the record supports ("Facts cited per
   record type" in the standards) with the rating from "Quality ratings". A fact the person does
   not have is created from the record (G8: date in RootsMagic's form with `rmutils.sort_date`,
   place and place detail under G21); a new person named with a stated relationship is added
   under G29/G35. Writes that no generic script covers (new facts, people, Residences with
   addresses) go in a one-off script in `notes/one_off/` (real names), with a dry run, as in
   step 5 of rm-record-cleanup. Census: one citation per household, cited on every member's
   facts; the couple's Marriage under G38/G39. Disagreements with the tree get a note on the
   event (G37); a disagreement the standards do not settle is a question for the user.
8. **Scan.** `scripts/media/attach_scan.py <tree> <citation> "<new path>"` (fills an empty
   AccessDate from the file date). Media details (G12, CLAUDE.md): Caption
   "Surname, Given – <record type> – <date>" (census: the head's name), RefNumber the official
   reference, Description the entry summary then where the image came from, Date and SortDate
   from the fact.
9. **Apply and push.** Each write: dry run, check it against the standards, apply, read back.
   Then `working_copy.py push`. A refused push (RootsMagic saved the test tree): fetch again,
   re-run, push (rm-record-cleanup step 0).
10. **Missing lists.** Run the rm-missing-records skill again with the degree shown in the header
    of `notes/missing/missing_censuses.md`, so the item drops out.
11. **Report.** One short table: file (new name and folder), citation, facts linked with ratings,
    new facts or people, renamed files. Then any question the standards did not settle.

## Folders, names and sources by record type

| Record | Folder under `H:\My Drive\Records` | Name | Source (ID) | Facts and ratings |
|---|---|---|---|---|
| Birth index (FreeBMD register page) | `Births\Britain\Registers` | `SUR-I-BRG-YYYY-Qn` | Birth Register - UK - FreeBMD (S583) | Birth PIX |
| Birth index (GRO online search) | `Births\Britain\GRO Searches` | `SUR-I-BRO-YYYY-Qn` (PDF) | Birth Register - UK - GRO (S707) | Birth PIX |
| Marriage index (FreeBMD register page) | `Marriage - Civil Registration\Britain\Register Images` | `SUR.I-MRB-YYYY-Qn` | Marriage Register - UK - FreeBMD (S587) | the couple's Marriage PIX; one citation per partner's entry |
| Death index (FreeBMD register page) | `Deaths\Britain\Registers` | `SUR-I-DRB-YYYY-Qn` | Death Register - UK - FreeBMD (S589) | Death PIX; Birth SIX (age), SDX (birth date, from 1969) |
| Death index (Ancestry, 1969 on) | `Deaths\Britain\Transcripts` | `SUR-I-DRB-YYYY-Qn` (PDF) | Death Register - UK - Ancestry (S704) | as above |
| Census England and Wales 1841-1911 | `Census\Britain\National\YYYY\Images` | `SUR-I-NIB-YYYY` | Census - England YYYY - Ancestry (1841 S560, 1851 S562, 1861 S563, 1871 S564, 1881 S565, 1891 S566, 1901 S567, 1911 S568) | Residence, Occupation; Birth; 1841-1901 PDX / SIX, 1911 PDO / SIO |
| Census 1921 | `Census\Britain\National\1921` | `SUR-I-NIB-1921-1`, `-2` (schedule, cover) | Census - England 1921 - Findmypast (S738) | PDO / SIO |
| 1939 Register | `Census\Britain\National\1939\Images` | `SUR-I-NIB-1939` | Register - England 1939 - Ancestry (S570) | Residence, Occupation PDX; Birth SDX |
| Census Ireland 1901, 1911 | `Census\Ireland\YYYY` | `SUR-I-NTB-1901-Pn`, `SUR-I-NII-1911-Pn` (PDF) | Census - Ireland YYYY - National Archives of Ireland (S572, S573) | PDO / SIO |
| Census US | `Census\US\National\YYYY` | `SUR-I-NIU-YYYY` | Census - US YYYY - Ancestry | PDX / SIX |

A record type not in the table: ask where it goes, then add a row here (and its source and
ratings to the standards if new).
