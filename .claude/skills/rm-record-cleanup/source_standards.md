# Source standards

Standing decisions for all record types, so they are not asked again. Set by the
user; the rm-record-cleanup skill applies them without asking. Decisions taken
during one record type's work (with real names) are in the git-ignored
`notes/<type>_issues.md`. This file is committed: no real names here.

## General (2026-10-16 to 2026-10-18)

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
| G10 | Transcription layout per provider: FreeBMD tab-separated columns under "Births/Deaths <quarter> <year>"; other providers "Label: value" lines without the tab after the label, without pasted source text |
| G11 | One citation per record per person: duplicates (one per fact) are merged. Census: one per household (see Facts) |
| G12 | One citation per scan. Scan caption "Surname, Given – <record type> – <date>" with the name as printed on the record; a scan with two entries gets one media row per entry |
| G13 | Scan file names that do not match the record are renamed, on the drive and in the tree |
| G14 | A citation with no scan is an issue for the end of the work |
| G15 | Entries are checked against the tree (ages, dates, places); only those that do not fit go to the user |
| G16 | AccessDate: the scan file's last-modified date |
| G17 | Cite on the event the record supports. A family citation only when the record itself shows the relationship (e.g. a certificate naming both partners or the parents); no citations on a person record as a whole |
| G18 | Where a website shows images of a published work (e.g. a newspaper), the work is the source and the website is where it was viewed: one source per newspaper title (title, place; viewed at the British Newspaper Archive); the citation holds the date, page and article. G1 and G3 apply where the website's own database is the source (indexes, transcriptions) |

## Facts cited per record type

| Record type | Facts |
|---|---|
| Birth index | Birth |
| Birth certificate | Birth; father's Occupation; Residence of both parents; parents' family |
| Death index | Death; Birth where an age or birth date is given |
| Marriage index | The couple's Marriage (family event); each partner's entry is its own citation on it |
| US state death index | Death; Birth; Burial and Occupation where given |
| Marriage certificate | The couple's Marriage; the family; each partner's Occupation, Residence and Birth (from the age); each father's Occupation; witnesses shared on the Marriage |
| Death certificate (UK) | Death (cause of death in its description); Birth (from the age, or the birth date from 1969); Occupation; informant's Residence; the family where it says "wife of"/"widow of"; usual address as Residence from 1969 |
| Death certificate (US state) | As the UK death certificate, plus Burial; Birth (date and place); the parents' family (as their child); the spouse's family; Residence |
| Irish civil birth and marriage registers | As the UK birth and marriage certificates |
| Hospital birth certificate | Birth |
| Notarial certificate of birth | Birth; parents' family |
| Baptism (parish register) | Christen; Birth where a birth date is given; the parents' family; the father's Occupation; the parents' Residence (abode) |
| Church marriage (parish register, from 1837) | As the marriage certificate |
| Burial (register) | Burial; Residence (abode); Birth (from the age); Death (date where given; where not, an undated Death becomes "before" the burial date) |
| Gravestone / memorial (photos, MIs, Find a Grave, CWGC) | Burial (place); Death; Birth (from the age); the family the stone names |
| Census | Each census-year fact becomes a Residence (census date, address); cited on it, Occupation and Birth (age and birthplace). One citation per household, reused on every member's facts (exception to G11); its scan caption uses the head's name |
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
| Death certificate (UK, GRO copy) | Occupation; family ("wife of"); usual address | SDX |
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
| Burial | Burial; Residence; Death (date given) | image PDO; index PDX |
| Burial | Death ("before" the burial) | image PIO; index PIX |
| Burial | Birth (from the age) | image SIO; index SIX |
| Gravestone / memorial | Burial (place); Death; family named on the stone | photo SDO; transcription (MIs, Find a Grave, CWGC) SDX |
| Gravestone / memorial | Birth (from the age) | photo SIO; transcription SIX |
| Census 1841-1901 (enumerator's book) | Residence; Occupation / Birth | PDX / SIX |
| Census 1911, 1921 (household form) | Residence; Occupation / Birth | PDO / SIO |
| Census, index only | Residence; Occupation / Birth | PDX / SIX |
| 1939 Register | Residence; Occupation / Birth (date given) | PDX / SDX |
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
