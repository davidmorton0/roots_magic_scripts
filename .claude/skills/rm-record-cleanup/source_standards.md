# Source standards

Standing decisions for all record types, so they are not asked again. Set by the
user; the rm-record-cleanup skill applies them without asking. Decisions taken
during one record type's work (with real names) are in the git-ignored
`notes/issues/<type>_issues.md`. This file is committed: no real names here.

## General (2026-10-16 to 2026-10-19)

| # | Standard |
|---|---|
| G1 | Online indexes and databases: template 6 (Complex Website) with AccessDate, SpecificItem, Citing. Certificates: free-form (template 0) to the Evidence Explained model |
| G2 | Source name: "<Record> - <Country> - <Provider>", naming what the record is (e.g. "Deaths - UK - GreyPower Deceased Data - Ancestry", not "Death Register") |
| G3 | One source per database; a different database gets its own source |
| G4 | Source text: a description of the source (what it is, where viewed), no URL (the URL field holds it); source comments cleared of text pasted from the website |
| G5 | Website owner and database title as shown when accessed (the saved page), not today's |
| G6 | A citation whose scan is an image from another site moves to that site's source, with a transcription read from the image |
| G7 | Cite the record on each fact it supports, never on a record event. Record events are deleted once their date and place are on the facts; where the person has no such fact, the record event is changed into it |
| G8 | A person with no fact for what the record shows: the fact is created from the record |
| G9 | Dates known only from a registration quarter: "before" the month after the quarter (Jan-Mar 1904 -> Bef Apr 1904). Known only from a registration month: "before" the month after it |
| G10 | Transcription layout per provider: FreeBMD tab-separated columns under "Births/Deaths/Marriages <quarter> <year>"; other providers "Label: value" lines without the tab after the label, without pasted source text. Marriage index: the partner's own line, then "Also on the page: <Surname Given>; ..." for the other names on the register page |
| G11 | One citation per record per person: duplicates (one per fact) are merged. Census: one per household (see Facts) |
| G12 | One citation per record. One record saved more than once (e.g. a web page and a certificate of the same entry) is one citation with each copy as a scan; the access date and transcription come from the newest copy (user, 2026-10-22). Scan caption "Surname, Given – <record type> – <date>" with the name as printed on the record; a scan with two entries gets one media row per entry |
| G13 | Scan file names that do not match the record are renamed, on the drive and in the tree |
| G14 | A citation with no scan is an issue for the end of the work only when a scan might be available (user, 2026-10-20). Where none is likely to be found (e.g. a text-only index), it is left as it is, provided the citation is referenced correctly |
| G15 | Entries are checked against the tree (ages, dates, places); only those that do not fit go to the user |
| G16 | AccessDate: the scan file's last-modified date, read before any rename or move (Google Drive gives a renamed or moved file a new date). With no scan: the access date in the website's own citation text where the transcription holds one (e.g. FamilySearch "Citing this Record"), otherwise left empty (user, 2026-10-20) |
| G17 | Cite on the event the record supports. A family citation only when the record itself shows the relationship (e.g. a certificate naming both partners or the parents); no citations on a person record as a whole |
| G18 | Where a website shows images of a published work (e.g. a newspaper), the work is the source and the website is where it was viewed: one source per newspaper title (title, place; viewed at the British Newspaper Archive); the citation holds the date, page and article. G1 and G3 apply where the website's own database is the source (indexes, transcriptions) |
| G19 | Scans in `unsure` and `Unsorted` folders are always ignored: not inventoried, attached, moved or asked about (user's rule, 2026-10-18) |
| G20 | Irish civil register images (irishgenealogy.ie): free-form source per event type, e.g. "Birth Register - Ireland - irishgenealogy.ie"; Footnote "Ireland, civil birth registration (copy register)"; Bibliography "Ireland. General Register Office. Birth registers (copies), 1864-. Images, irishgenealogy.ie."; Page "<name>, born <date>; registered <date>, <SRD> superintendent registrar's district, <RD> registrar's district, entry <n>; image, irishgenealogy.ie, group registration ID <id>, accessed <date>". Marriages (user, 2026-10-21): "Marriage Register - Ireland - irishgenealogy.ie"; Footnote "Ireland, civil marriage registration (copy register)"; Bibliography "Ireland. General Register Office. Marriage registers (copies), 1845-. Images, irishgenealogy.ie."; Page "<groom> and <bride>, married <date>, <place>; <RD> registrar's district, entry <n>; image, irishgenealogy.ie, group registration ID <id>, accessed <date>" |
| G21 | Addresses (user's choice, 2026-10-19): a street or house address is a place detail (PlaceType 2) under the town, and the fact holds both (PlaceID the town, SiteID the detail). The detail is named as the record writes it, house number included. An existing detail with the same name under the same town is reused; a different house number is a different detail; the same address held twice is merged (events moved to one, the other deleted). A record giving only a town: the town, no detail. Addresses are never put in the fact's description. In a GEDCOM export RootsMagic writes the detail as ADDR and the town as PLAC |
| G22 | A Birth known only from an age (user's choice, 2026-10-19): "between" the month after the event's month, age + 1 years earlier, and the event's month, age years earlier (age 25 on 30 Apr 1896 -> Bet May 1870 and Apr 1871, `DR+18700500..+18710400..`). Used when a new Birth fact is created from the age (G8); an existing Birth date is not changed |
| G23 | All evidence is cited on the event it bears on, even where it disagrees with the event (e.g. an age that gives a different birth year). The disagreement still goes to the issues at the end (G15) (user's rule, 2026-10-21) |
| G24 | GRO digital images (register entries viewed online from the GRO, "E/W Death Digital Image" and the like): their own free-form source, separate from certificates, e.g. "Death Register - UK - GRO Digital Images"; Footnote "England, death registration (GRO digital image)"; Bibliography "England. General Register Office. Death registers (digital images). General Register Office, Southport."; Page "<name>, died <date>, <place>; registered <date>, <district> district, <quarter> quarter <year>, vol. <v>, p. <p>, entry <n>; digital image, General Register Office, viewed <date>"; the order number in the source text, not in Page; ratings as the certificate copies (user, 2026-10-21) |
| G25 | Evidence from another record type: when the work on one record type turns up evidence from a record of another type (e.g. an occupation in a Death description that came from a probate entry), it is applied now under that type's standard (an Occupation fact cited to the probate citation, probate rating). The citation's own clean-up (source form, transcription, other links) waits for its record type (user, 2026-10-22) |
| G26 | Event descriptions: an event's description holds only details of that event (for a Death, the cause of death). Text that belongs to another fact (an occupation, a relationship, an address) is moved to that fact, created if needed, and that fact is cited to the record the text came from. If no cited record on the event gives that text, it stays and goes to the issues (user, 2026-10-22) |
| G27 | Informants with no stated relationship (e.g. "G Capper, in attendance"): matched to the deceased's household or immediate family (spouse, parents, children, siblings); where exactly one person there has that name, they are the informant. None or more than one: transcription only (G28). Otherwise as the informant decision of the record type (user, 2026-10-22) |
| G28 | A person named on a record (informant, witness and the like) whose relationship to someone in the tree cannot be clearly established is not added to the tree: transcription only, without a question (user's rule, 2026-10-22) |
| G29 | Parents and spouses named on a record with the relationship stated, but not in the tree, are added as people with that family (parents' family or spouse's family), and the family is cited with the record type's family rating (user, 2026-10-22) |
| G30 | A date corrected on the evidence: the note on the fact gives the evidence for the new date. The old value is not mentioned when no evidence for it was seen (e.g. an uncited Birth year) (user, 2026-10-23) |
| G31 | Birth date against ages (census, death and the like): where the Birth rests on an accurate source (birth register or index, certificate, christening) and less accurate records disagree, the accurate date is kept and a note on the Birth gives each record's age and the years it gives (e.g. "The 1921 census age (62y5m) gives about Jan 1859; the birth index gives Jan-Mar 1858."), without a question. Ask the user only when one record is 4 or more years off, or when all the other records are at least 2 years off in the same direction (user, 2026-10-23) |
| G32 | Birth with no accurate date evidence (no birth register or index, certificate or christening) and records whose ages disagree: the Birth becomes a "between" range covering every record (e.g. `DR+18440000..+18490000..`), with a note on the Birth giving each record's age and the years it gives (G30), without a question (user, 2026-10-23) |
| G33 | A person whose primary name has an empty Given and a given name in Surname (e.g. Surname "Mary"): the name moves to Given and Surname is left empty (maiden name unknown). A married name shown on a record is added as an alternative (AKA) name cited to that record. Surname-only people whose Surname is a real surname (e.g. "Maxfield"), "Unknown" or empty are not changed; they go to the issues (user, 2026-10-23) |
| G34 | Oral history (what relatives who knew the person said): one free-form source (template 0) per informant, named "Oral history - <informant>"; one citation per statement, holding what was said; cited on the fact or name it supports (e.g. an alternative name) (user, 2026-10-23) |
| G35 | People named on a record with their relationship to someone in the tree stated (e.g. son, daughter, wife on a census), not already in the tree, are added when the evidence is reasonable: with their family (parents' family, spouse's family), a Birth from the age (G22) and the record cited on their facts (extends G29 beyond parents and spouses). G28 still applies where the relationship is not clearly established (user's rule, 2026-10-23) |
| G36 | Identification: the question for a linked record is "is this record correct for the person in the tree?". Answered "not sure", the record is removed from the tree for later checking (its scan, if any, goes to the type's `unsure` folder). A record with no scan or copy held is no record: its citation, links, record events and media rows are deleted. Other candidate records for the person are separate questions. Always check with the user before removing a record under this rule (user's rule, 2026-10-23) |
| G37 | Any discrepancy between a cited record and the event it is cited on (age, date, place, name) gets a note on the event giving what the record says, whatever else is decided (user's rule, 2026-10-23) |
| G38 | Census and 1939 Register as evidence of marriage: where both partners live at the same address, both are shown as married, and no one else in the household is marked as married, the household citation is also cited on the couple's Marriage (user's rule, 2026-10-24) |
| G39 | Census and 1939 Register, couple with no Marriage fact: where a G38 household shows the couple as head and wife, both married, a Marriage is created for the family, dated "before" the earliest such census date (`DB+YYYYMMDD..+00000000..`), no place, cited to each such household citation with the G38 rating, with a note per census: "<year> census: <head> (head, married, <age>) and <wife> (wife, married, <age>), living together." (names and ages as on the record). A couple shown otherwise (e.g. son-in-law and daughter of the head) goes to the issues (user's rule, 2026-10-24) |

## Facts cited per record type

| Record type | Facts |
|---|---|
| Birth index | Birth |
| Birth certificate | Birth; father's Occupation; Residence of both parents; parents' family |
| Death index | Death; Birth where an age or birth date is given |
| Marriage index | The couple's Marriage (family event); each partner's entry is its own citation on it |
| US state death index | Death; Birth; Burial and Occupation where given |
| Marriage certificate | The couple's Marriage; the family; each partner's Occupation, Residence and Birth (from the age); each father's Occupation; witnesses shared on the Marriage |
| Death certificate (UK) | Death (cause of death in its description); Birth (from the age, or the birth date from 1969); Occupation; informant's Residence; the family where it says "wife of"/"widow of"/"daughter of", and that husband's or father's Occupation (dated the death; "before" it for a widow) (user, 2026-10-21); usual address as Residence from 1969 |
| Death certificate (US state) | As the UK death certificate, plus Burial; Birth (date and place); the parents' family (as their child); the spouse's family; Residence |
| Irish civil birth and marriage registers | As the UK birth and marriage certificates |
| Hospital birth certificate | Birth |
| Notarial certificate of birth | Birth; parents' family |
| Baptism (parish register) | Christen; Birth where a birth date is given; the parents' family; the father's Occupation; the parents' Residence (abode) |
| Church marriage (parish register, from 1837) | As the marriage certificate |
| Banns book entry | The couple's "Marriage Bann" family fact (fact 305), dated the first reading; its own citation (G12) |
| Marriage licence bond or allegation | The couple's "Marriage License" family fact (fact 307), dated the bond; its own citation (G12) |
| US state marriage index | The couple's Marriage and family; each partner's Birth where an age is given |
| US marriage licence docket | The couple's Marriage and family; "Marriage License" family fact (307) dated the licence issue; each partner's Residence and Occupation (dated the marriage) and Birth (date and place given) |
| Burial (register) | Burial; Residence (abode); Birth (from the age); Death (date where given; where not, an undated Death becomes "before" the burial date) |
| Gravestone / memorial (photos, MIs, Find a Grave, CWGC) | Burial (place); Death; Birth (from the age); the family the stone names. A person with no Burial gets one at the churchyard, dated "after" the death date (`DA+YYYYMMDD..+00000000..`) (user, 2026-10-22) |
| Census | Each census-year fact becomes a Residence (census date, address); cited on it, Occupation and Birth (age and birthplace). One citation per household, reused on every member's facts (exception to G11); its scan caption uses the head's name; the couple's Marriage under G38 |
| 1939 Register; Irish, US and Scottish censuses | As the census |
| Trade directory | Residence and Occupation, dated the directory's year |
| Electoral register | Residence, dated the register's year |
| Probate calendar entry; copy of a will | The grant (Probate or Administration fact, value in its description); Death (date and place); Residence (address at death); Occupation; the family where a relationship is stated ("widow", "son") |
| Newspaper article | Each fact it states (Death, Burial, Marriage, Occupation, Residence, family) |
| Online family tree | The facts it states (kept as citations) |
| Military service and pension records | Military service; Residence; Occupation; Birth; family (next of kin) |
| School admission register | Education; Residence; Birth (date given); parent's family |
| Passenger list | Emigration or Immigration; Occupation; Birth (from age) |
| Passport; naturalisation | The event; Residence; Occupation; Birth (date and place) |
| Emigration index | Emigration |
| Ulster Covenant | Residence (address signed from); Signing |

## Quality ratings

Three letters: information P primary / S secondary; evidence D direct / I indirect;
source O original / X derivative. "Image" = an image of the document itself;
"index" = an index or transcription only.

| Record | Fact | Rating |
|---|---|---|
| GRO birth index entry | Birth | PIX |
| GRO marriage index entry | Marriage | PIX |
| GRO death index entry | Death | PIX |
| GRO death index entry | Birth, before 1969 (age) | SIX |
| GRO death index entry | Birth, from 1969 (birth date) | SDX |
| FamilySearch Irish birth index | Birth | PIX |
| US state death index entry | Death; Burial; Occupation | PDX |
| US state death index entry | Birth, birth date given / "abt" or age only | SDX / SIX |
| Birth certificate (GRO copy) | Birth; father's Occupation; informant's Residence | PDX |
| Birth certificate (GRO copy) | Other parent's Residence; parents' family | PIX |
| Marriage certificate (GRO copy) | Marriage; family; witnesses; each partner's Occupation and Residence | PDX |
| Marriage certificate (GRO copy) | Each father's Occupation | SDX |
| Marriage certificate (GRO copy) | Each partner's Birth (from the age) | SIX |
| Death certificate (UK, GRO copy) | Death; informant's Residence | PDX |
| Death certificate (UK, GRO copy) | Occupation; family ("wife of"); husband's or father's Occupation; usual address | SDX |
| Death certificate (UK, GRO copy) | Birth from the age / birth date given (from 1969) | SIX / SDX |
| Death certificate (US state) | As the UK death certificate, plus Burial | PDX |
| Death certificate (US state) | Birth date and place; parents' family; spouse's family; Residence | SDX |
| Irish civil birth and marriage register images (GRONI, irishgenealogy.ie) | As the UK birth and marriage certificates (copy registers, so X) | as UK |
| Hospital birth certificate (original document held) | Birth | PDO |
| Notarial certificate of birth | Birth; parents' family | PDX |
| Baptism | Christen; Birth (date given); parents' family; father's Occupation; Residence | image PDO; index PDX |
| Church marriage | Marriage; family; witnesses; partners' Occupation and Residence | image PDO; index PDX |
| Church marriage | Fathers' Occupation | image SDO; index SDX |
| Church marriage | Partners' Birth (from an age; none for "of full age") | image SIO; index SIX |
| Banns book entry | Marriage Bann | image PDO; index PDX |
| Marriage licence bond or allegation | Marriage License | image PDO; index PDX |
| US state marriage index entry | Marriage; family / Birth (from the age) | PDX / SIX |
| US marriage licence docket | Marriage; family; Marriage License; partners' Residence and Occupation / partners' Birth (date given) | image PDO / SDO |
| Burial | Burial; Residence; Death (date given) | image PDO; index PDX |
| Burial | Death ("before" the burial) | image PIO; index PIX |
| Burial | Birth (from the age) | image SIO; index SIX |
| Bishop's transcript (image of the copy sent to the bishop), any parish register event | As the register entry, with X for the copy: e.g. burial PDX / PIX / SIX (user, 2026-10-22) | as index |
| Gravestone / memorial | Burial (place); Death; family named on the stone | photo SDO; transcription (MIs, Find a Grave, CWGC) SDX |
| Gravestone / memorial | Birth (from the age) | photo SIO; transcription SIX |
| Gravestone / memorial website (e.g. Find a Grave) | Birth date or year stated on the page | SIX (user, 2026-10-22) |
| Census 1841-1901 (enumerator's book) | Residence; Occupation / Birth | PDX / SIX |
| Census 1911, 1921 (household form) | Residence; Occupation / Birth | PDO / SIO |
| Census, index only | Residence; Occupation / Birth | PDX / SIX |
| 1939 Register | Residence; Occupation / Birth (date given) | PDX / SDX |
| Census or 1939 Register (G38) | Marriage | 1841-1901 PIX; 1911, 1921 PIO; 1939 PIX; index only PIX (user, 2026-10-24) |
| Irish census 1901, 1911 (household forms) | Residence; Occupation / Birth | PDO / SIO |
| US census 1880-1940 | Residence; Occupation / Birth | PDX / SIX |
| Scottish census | Residence; Occupation / Birth | PDX / SIX |
| Trade directory | Residence; Occupation | SDX |
| Electoral register | Residence | SDX |
| Probate calendar entry | Grant / Death; Residence; Occupation; family | PDX / SDX |
| Copy of a will (Probate Registry) | Grant; family named in the will / Death; Residence; Occupation | PDX / SDX |
| Newspaper family notice (birth, marriage, death) | Facts it states | PDO |
| Newspaper report | Facts it states | SDO |
| Newspaper, age or birth worked out | Birth | SIO |
| Online family tree (someone else's) | Facts it states | SIX |
| Military service and pension records | Military service; Residence; Occupation; family / Birth | image PDO / SDO; index PDX / SDX |
| School admission register | Education; Residence; parent's family / Birth (date given) | image PDO / SDO; index PDX / SDX |
| Passenger list | Emigration or Immigration; Occupation / Birth (from age) | image PDO / SIO; index PDX / SIX |
| Passport; naturalisation | The event; Residence; Occupation / Birth (date and place) | image PDO / SDO; index PDX / SDX |
| Emigration index | Emigration | PDX |
| Ulster Covenant | Residence; Signing | image PDO; index PDX |

## Record types still to define

All groups defined (2026-10-18). New record types are added to the tables above as they come up.
