# Scan details per record type (machine-readable)

Read by `scripts/media/evaluate_scans.py`. Draft (2026-10-28) from the scans already cleaned up;
corrected by the user. Committed: no real names.

## Standards (CLAUDE.md "Media details convention" and `rm-record-cleanup/source_standards.md`)

| # | Standard |
|---|---|
| M1 | Caption "Surname, Given – record type – YYYY Qn" (the Media page sorts by caption); with the name as printed on the record (G12) |
| M2 | RefNumber: the official reference (GRO index: "YYYY Qn District Volume Page"; certificate: its number) |
| M3 | Description: the entry's transcription (summary), then where the image came from |
| M4 | Date with its SortDate: the date of the event the citation supports. Form only is checked; a valid Date is trusted (the fact date and the source date can differ: open) |
| G12 | A scan with two entries gets one media row per entry; one record saved more than once is one citation with each copy as a scan |
| G13 | Scan file names that do not match the record are renamed, on the drive and in the tree |
| G19 | Scans in `unsure` and `Unsorted` folders are always ignored |
| L1 | PDFs are stored as File (MediaType 2), images as Image (MediaType 1) (CLAUDE.md) |

## Scan forms

A scan takes the first row whose Name matches the source of a citation it is attached to.
Caption, RefNumber, Description and File: the form (`*` any text, `a|b` either); `-` not checked;
a value that must be filled but has no fixed form is `*`. The en dash ( – ) in captions is part
of the form.

| Scans | Name | Caption | RefNumber | Description | File |
|---|---|---|---|---|---|
| GRO birth index image | `Birth Register - UK - FreeBMD` | `*, * – birth index – * Q*\|*, * – birth index – * *` | `* Q* * * *\|* * * * *` | `Births registered in *` | `*-BRG-*` |
| GRO marriage index image | `Marriage Register - UK - FreeBMD` | `*, * – marriage index – * Q*\|*, * – marriage index – * *` | `* Q* * * *\|* * * * *` | `Marriages registered in *` | `*-MRB-*` |
| GRO death index image | `Death Register - UK - FreeBMD` | `*, * – death index – * Q*\|*, * – death index – * *` | `* Q* * * *\|* * * * *` | `Deaths registered in *` | `*-DRB-*` |
| GRO death index entry (Ancestry) | `Death Register - UK - Ancestry` | `*, * – death index – *` | `*` | `Deaths registered in *` | `*-DRB-*` |
| Census, 1939 Register | `Census - * or Register - England 1939 - *` | `*, * – census – *` | `*` | `*` | `*-N*-*` |
| Birth certificate | `Birth Certificate - UK` | `*, * – birth certificate – *` | `*` | `Birth registered *` | `*-BCT-*` |
| Marriage certificate | `Marriage Certificate - UK` | `* – marriage certificate – *` | `*` | `Marriage *` | `*-MIB-*` |
| Death certificate | `Death Certificate - UK` | `*, * – death certificate – *` | `*` | `Death registered *` | `*-DCB-*` |
| GRO digital image, death | `Death Register - UK - GRO Digital Images` | `*, * – death register – *` | `* Q* * * *` | `Death registered *` | `*-DCB-*` |
| Irish birth register | `Birth Register - Ireland - irishgenealogy.ie` | `*, * – birth register – *` | `*` | `Birth registered *` | `*-CII-*` |
| Irish marriage register | `Marriage Register - Ireland - irishgenealogy.ie` | `* – marriage register – *` | `*` | `*` | - |
| Baptism index entry (FamilySearch) | `Baptisms - England - England Births and Christenings - FamilySearch` | `*, * – baptism index – *` | - | `Entry for *` | `*-CTB-*` |
| Baptism, burial or marriage (FreeREG) | `Parish Registers - England - FreeREG` | `*, * – baptism – *\|*, * – burial – *\|* – marriage – *` | `*` | `*` | - |
| Parish register (other) | `Parish Registers - *` | `*, * – baptism – *\|*, * – burial – *\|* – marriage – *\|* – church marriage – *` | - | `*` | - |
| Church marriage, banns, marriage index | `Church Marriages - * or Marriages - *` | `* – church marriage – *\|* – marriage index – *\|* – marriage – *\|* – banns – *` | - | `*` | - |
| Death index (other) | `Deaths - UK - * or Death Register - UK Marine - * or Deaths - USA - * Index - Ancestry or Deaths - USA - * Deaths Index - Ancestry` | `*, * – death index – *` | - | `*` | - |
| Birth index (FamilySearch, Ireland) | `Birth Register - Ireland - FamilySearch` | `*, * – birth index – *` | - | `*` | - |
| Baptism | `Baptisms - *` | `*, * – baptism – *\|*, * – baptism index – *` | - | `*` | - |
| Burial | `Burials - *` | `*, * – burial – *\|*, * – burial index – *` | - | `*` | `*-BIB-*\|*-BTB-*` |
| Gravestone, memorial page | `Graves - *` | `*, * – gravestone – *\|*, * – Find a Grave memorial – *\|*, * – monumental inscription – *` | - | `*` | - |
| Death certificate (US state) | `Deaths - USA - * Certificates - Ancestry` | `*, * – death certificate – *` | `*` | `*` | `*-DCU-*` |
