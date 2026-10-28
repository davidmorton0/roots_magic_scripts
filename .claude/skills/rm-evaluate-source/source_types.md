# Source types and source standards

The standards a source row and its citations must meet, one row per source type with its required
form, and one row per citation form. `scripts/sources/evaluate_source.py` reads the table under
"Source types", `scripts/citations/evaluate_citation.py` the table under "Citation forms"; each
flags every row that does not fit. This file is committed: no real names here (use `*` in name patterns).

## Source standards (copied 2026-10-28 from `rm-record-cleanup/source_standards.md`, which keeps them too)

| # | Standard |
|---|---|
| G1 | Online indexes and databases: template 6 (Complex Website) with AccessDate, SpecificItem, Citing. Certificates: free-form (template 0) to the Evidence Explained model |
| G2 | Source name: "<Record> - <Country> - <Provider>", naming what the record is (e.g. "Deaths - UK - GreyPower Deceased Data - Ancestry", not "Death Register") |
| G3 | One source per database; a different database gets its own source |
| G4 | Source text: a description of the source (what it is, where viewed), no URL (the URL field holds it); source comments cleared of text pasted from the website |
| G5 | Website owner and database title as shown when accessed (the saved page), not today's |
| G6 | A citation whose scan is an image from another site moves to that site's source, with a transcription read from the image |
| G18 | Where a website shows images of a published work (e.g. a newspaper), the work is the source and the website is where it was viewed: one source per newspaper title (title, place; viewed at the British Newspaper Archive); the citation holds the date, page and article. G1 and G3 apply where the website's own database is the source (indexes, transcriptions) |
| G20 | Irish civil register images (irishgenealogy.ie): free-form source per event type; form in the table below |
| G24 | GRO digital images (register entries viewed online from the GRO): their own free-form source, separate from certificates; the order number in the source text, not in Page; form in the table below |
| G34 | Oral history: one free-form source (template 0) per informant, named "Oral history - <informant>"; form in the table below |
| L1 | Fields are saved without a byte-order mark or XML declaration, as RootsMagic 12 saves source rows (CLAUDE.md; rm-record-cleanup step 5.1) |
| L2 | Template 6 source fields: DatabaseTitle, Descriptor, WebsiteTitle and URL filled; DatabaseCreator empty. Template 0 source fields: Footnote, ShortFootnote and Bibliography filled. Draft, taken from every source cleaned up so far (2026-10-28); to be confirmed by the user |
| L3 | A source with no citations is flagged; the user decides whether it is deleted |

## Source types

Draft (2026-10-28), taken from the sources already cleaned up; corrected by the user. Columns:

- Name: the source name; `*` stands for any text. Several patterns are separated by " or ".
  A source takes the first row whose name matches and whose template is the same; failing
  that, the first row whose name matches.
- Template: the TemplateID the source must have.
- Required: source fields that must be filled, besides those of L2.
- Fixed: source fields that must hold exactly this value (`a|b`: either). `{1}` is the text the
  first `*` of the name stood for. A field given as `Field=` must be empty.
- Text: the source text (ActualText) it must hold, or `-` for any description (G4).

| Type | Name | Template | Required | Fixed | Text |
|---|---|---|---|---|---|
| FreeBMD index | `* Register - UK - FreeBMD` | 6 | WebsiteCreator | Descriptor=database with images; WebsiteCreator=Free UK Genealogy; WebsiteTitle=FreeBMD; URL=https://www.freebmd.org.uk | - |
| FreeCEN transcription | `Census - * - FreeCEN` | 6 | WebsiteCreator | DatabaseTitle=FreeCEN census transcriptions; Descriptor=database; WebsiteCreator=Free UK Genealogy; WebsiteTitle=FreeCEN; URL=https://www.freecen.org.uk | - |
| FreeREG transcription | `Parish Registers - England - FreeREG` | 6 | WebsiteCreator | DatabaseTitle=FreeREG; Descriptor=database; WebsiteCreator=FreeREG; WebsiteTitle=FreeREG; URL=https://www.freereg.org.uk | - |
| GRO online index | `* Register - UK - GRO` | 6 | | Descriptor=database; WebsiteTitle=General Register Office; URL=https://www.gro.gov.uk | - |
| Ancestry database | `* - Ancestry` | 6 | WebsiteCreator | Descriptor=database\|database with images; WebsiteTitle=Ancestry; URL=https://www.ancestry.co.uk | - |
| Findmypast database | `* - Findmypast` | 6 | WebsiteCreator | Descriptor=database\|database with images; WebsiteTitle=Findmypast; URL=https://www.findmypast.co.uk | - |
| FamilySearch database | `* - FamilySearch` | 6 | | Descriptor=database\|database with images; WebsiteCreator=; WebsiteTitle=FamilySearch; URL=https://www.familysearch.org | - |
| Find a Grave | `Graves - International - Find a Grave` | 6 | WebsiteCreator | DatabaseTitle=Find a Grave; Descriptor=database and images; WebsiteCreator=Find a Grave; WebsiteTitle=Find a Grave; URL=https://www.findagrave.com | - |
| Irish census | `Census - Ireland * - National Archives of Ireland` | 6 | WebsiteCreator | DatabaseTitle=Census of Ireland 1901/1911; Descriptor=database with images; WebsiteCreator=National Archives of Ireland; WebsiteTitle=Census of Ireland 1901/1911; URL=http://www.census.nationalarchives.ie | - |
| UK birth certificate | `Birth Certificate - UK` | 0 | | Footnote=England, birth certificate (certified copy); ShortFootnote=England, birth certificate (certified copy); Bibliography=England. Registrar General. Birth Certificates. General Register Office, Southport. | - |
| UK marriage certificate | `Marriage Certificate - UK` | 0 | | Footnote=England, marriage certificate (certified copy); ShortFootnote=England, marriage certificate (certified copy); Bibliography=England. Registrar General. Marriage Certificates. General Register Office, Southport. | - |
| UK death certificate | `Death Certificate - UK` | 0 | | Footnote=England, death certificate (certified copy); ShortFootnote=England, death certificate (certified copy); Bibliography=England. Registrar General. Death Certificates. General Register Office, Southport. | - |
| GRO digital image, death (G24) | `Death Register - UK - GRO Digital Images` | 0 | | Footnote=England, death registration (GRO digital image); ShortFootnote=England, death registration (GRO digital image); Bibliography=England. General Register Office. Death registers (digital images). General Register Office, Southport. | - |
| Irish civil birth register (G20) | `Birth Register - Ireland - irishgenealogy.ie` | 0 | | Footnote=Ireland, civil birth registration (copy register); ShortFootnote=Ireland, civil birth registration (copy register); Bibliography=Ireland. General Register Office. Birth registers (copies), 1864-. Images, irishgenealogy.ie. | - |
| Irish civil marriage register (G20) | `Marriage Register - Ireland - irishgenealogy.ie` | 0 | | Footnote=Ireland, civil marriage registration (copy register); ShortFootnote=Ireland, civil marriage registration (copy register); Bibliography=Ireland. General Register Office. Marriage registers (copies), 1845-. Images, irishgenealogy.ie. | - |
| Hospital birth certificate, Shanghai | `Birth Certificate - China - Shanghai Hospital` | 0 | | Footnote=China, Shanghai, medical birth certificate; ShortFootnote=China, Shanghai, medical birth certificate; Bibliography=China. Ministry of Health. Medical Birth Certificates. Shanghai. | - |
| Notarial certificate of birth, Shanghai | `Notarial Certificate of Birth - China - Shanghai Notary` | 0 | | Footnote=China, Shanghai, notarial certificate of birth; ShortFootnote=China, Shanghai, notarial certificate of birth; Bibliography=China. Shanghai. Notary Public Office. Notarial Certificates of Birth. | - |
| Oral history (G34) | `Oral history - *` | 0 | | Footnote={1}, oral history (told to the compiler); ShortFootnote={1}, oral history; Bibliography={1}. Oral history, told to the compiler. | What {1}, who knew the people concerned, told the compiler |
| Register or gravestone image, origin not known | `* - Photograph or * - Photographs or * - Image` | 0 | | | - |
| Own photographs (private collection) | `* - Photographs` | 10005 | Collection | Repository=Private collection | - |
| Printed index or book | `* - Nottinghamshire Record Series or * - Nottinghamshire FHS` | 0 | | | - |
| Published book (template) | `* - Nottinghamshire FHS` | 10021 | Author, Title, PubPlace, Publisher, PubDate | | - |

## Citation standards (G rules copied 2026-10-28 from `rm-record-cleanup/source_standards.md`)

| # | Standard |
|---|---|
| G10 | Transcription layout per provider: FreeBMD tab-separated columns under "Births/Deaths/Marriages <quarter> <year>"; other providers "Label: value" lines without the tab after the label, without pasted source text. Marriage index: the partner's own line, then "Also on the page: <Surname Given>; ..." for the other names on the register page |
| G11 | One citation per record per person: duplicates (one per fact) are merged. Census: one per household |
| G12 | One citation per record. One record saved more than once is one citation with each copy as a scan; the access date and transcription come from the newest copy |
| G14 | A citation with no scan is an issue only when a scan might be available; where none is likely (e.g. a text-only index), it is left as it is |
| G16 | AccessDate: the scan file's last-modified date, read before any rename or move. With no scan: the access date in the website's own citation text where the transcription holds one, otherwise left empty |
| C1 | CitationName is the citation field values joined with "; " in template order, an empty field as an empty part (e.g. "; entry for ...; ..." with no AccessDate) (free-form: the Page text) (CLAUDE.md; 19 of the 20 template 6 citations with an empty field, 2026-10-28) |
| C2 | Transcription lines end with CR LF, as RootsMagic writes them (rm-record-cleanup step 3) |
| C3 | AccessDate written as "7 August 2020" (day, month name, year), as in existing citations |
| C4 | New or completed FreeBMD citations end with the FreeBMD citation link (`https://www.freebmd.org.uk/cgi/information.pl?cite=...&scan=1`); the user supplies it (CLAUDE.md) |

## Citation forms

Draft (2026-10-28), taken from the citations already cleaned up; corrected by the user. A citation
takes the first row whose Name matches its source's name. Columns:

- Fields: citation fields with the form they must have (`*` stands for any text, `a|b`: either).
  Census: a person outside their own household is cited as "<name>, <role>, <place>" (`*, *`).
- Transcription: `index` (a "Births/Deaths/Marriages ..." header line, then tab-separated entry
  lines), `labels` (starts with "Label: value" lines), or `-` (not checked).
- Last line: the form of the transcription's last line, or `-`.

| Form | Name | Fields | Transcription | Last line |
|---|---|---|---|---|
| FreeBMD index entry | `* Register - UK - FreeBMD` | SpecificItem=entry for *, vol. *, p. *; Citing=General Register Office, * registered in * | index | `https://www.freebmd.org.uk/cgi/information.pl?cite=*` |
| GRO online index entry | `* Register - UK - GRO` | SpecificItem=entry for *, vol. *, p. *; Citing=General Register Office, * registered in * | - | - |
| GRO death index entry, Ancestry | `Death Register - UK - Ancestry` | SpecificItem=entry for *, born *, registered *, entry *\|entry for *, born *, registered *, vol. *, p. *; Citing=General Register Office, England and Wales Civil Registration Indexes | index | - |
| FreeCEN census entry | `Census - * - FreeCEN` | Citing=The National Archives, * | labels | - |
| Census household, England and Wales | `Census - England * - Ancestry or Census - England * - Findmypast or Register - England 1939 - Ancestry` | SpecificItem=household of *\|*, *; Citing=The National Archives, * | labels | - |
| Census household, Scotland | `Census - Scotland * - Ancestry` | SpecificItem=household of *\|*, *; Citing=General Register Office for Scotland, census * | labels | - |
| Census household, US | `Census - US * - Ancestry` | SpecificItem=household of *\|*, *; Citing=Year: *; Census Place: * | labels | - |
| Census household, Ireland | `Census - Ireland * - National Archives of Ireland` | SpecificItem=household of *; Citing=National Archives of Ireland, census * | - | - |
| FreeREG entry | `Parish Registers - England - FreeREG` | Citing=* parish register, transcribed by *; https://www.freereg.org.uk/*\|* parish register, FreeREG file * | labels | - |
| Find a Grave page or photograph | `Graves - International - Find a Grave` | SpecificItem=memorial page for *, Find a Grave Memorial no. *\|photograph of the gravestone of *, Find a Grave Memorial no. *; Citing=*; maintained by *\|*; photo added by * | - | - |
| UK birth certificate | `Birth Certificate - UK` | Page=*, born *; registered * quarter *, * district, * sub-district, entry *; certificate *, issued *, General Register Office, Southport | labels | - |
| UK marriage certificate | `Marriage Certificate - UK` | Page=* and *, married *; * district, entry *; certificate *, issued *, General Register Office, Southport | labels | - |
| UK death certificate | `Death Certificate - UK` | Page=*, died *; registered * quarter *, * district, * sub-district, entry *; certificate *, issued * | labels | - |
| GRO digital image, death (G24) | `Death Register - UK - GRO Digital Images` | Page=*, died *; registered *, * district, * quarter *, vol. *, p. *, entry *; digital image, General Register Office, viewed * | labels | - |
| Irish civil birth register (G20) | `Birth Register - Ireland - irishgenealogy.ie` | Page=*, born *; registered *, * superintendent registrar's district, * registrar's district, entry *; image, irishgenealogy.ie, group registration ID *, accessed * | labels | - |
| Irish civil marriage register (G20) | `Marriage Register - Ireland - irishgenealogy.ie` | Page=* and *, married *, *; * registrar's district, entry *; image, irishgenealogy.ie, group registration ID *, accessed * | labels | - |
| Oral history (G34) | `Oral history - *` | | - | - |

## Not yet defined

Sources that match no row are flagged "no source type". Before fixing one, agree its type with
the user and add a row here. Groups found on 2026-10-28 with no row yet: newspapers (template
10013, 61 sources; G18), wills and probate (10018, 10019), electoral registers, school and other
local records (10006), directories (10004, 10026), military (10010, 10023), travel and
naturalisation (10012, 10014, 10024), family trees (0, 10025), the Commonwealth War Graves
Commission (10008), and older free-form sources named after a place or a person.
