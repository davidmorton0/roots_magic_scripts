# Quality ratings (machine-readable)

Read by `scripts/citations/evaluate_quality.py`. Draft (2026-10-28) from the "Quality ratings"
table in `rm-record-cleanup/source_standards.md` and the ratings of the records already cleaned
up; corrected by the user. Committed: no real names.

Three letters (CitationLinkTable.Quality, RootsMagic 12): information P primary / S secondary;
evidence D direct / I indirect / N negative; source O original / X derivative; `~` not set.
`~~~` is not assessed.

## Ratings

A link takes the first row whose Name matches its source's name, whose Fact is the linked fact
(`family`, `name`) and whose Condition holds.

- Condition: `Field~regex` on a citation field (`Text` is the transcription), or `-`.
- Condition: SpecificItem falls back to Page for free-form citations.
- Rating: the expected quality; `a|b` either. `{O/X}`: O where the source holds images of the
  record (its Descriptor holds "image", or it is named "... - Photograph(s)" or "... - Image")
  and the citation has an image scan (JPEG, TIFF, PNG ...) attached; X otherwise (index entries
  of such a source have no image; an image of a copy, e.g. a bishop's transcript, is flagged for review).

| Record | Name | Fact | Condition | Rating |
|---|---|---|---|---|
| GRO birth index entry | `Birth Register - UK - FreeBMD or Birth Register - UK - GRO` | Birth | - | PIX |
| FamilySearch Irish birth index | `Birth Register - Ireland - FamilySearch` | Birth | - | PIX |
| GRO marriage index entry | `Marriage Register - UK - FreeBMD` | Marriage | - | PIX |
| GRO death index entry | `Death Register - UK - FreeBMD or Death Register - UK - Ancestry or Death Register - UK Marine - Findmypast or Deaths - UK - *` | Death | - | PIX |
| GRO death index entry, birth date given | `Death Register - UK - FreeBMD or Death Register - UK - Ancestry or Death Register - UK Marine - Findmypast or Deaths - UK - *` | Birth | SpecificItem~born | SDX |
| GRO death index entry, age | `Death Register - UK - FreeBMD or Death Register - UK - Ancestry or Death Register - UK Marine - Findmypast or Deaths - UK - *` | Birth | - | SIX |
| Index entries: alternative name | `* Register - UK - FreeBMD` | name | - | PIX |
| US state death index entry | `Deaths - USA - * Index - Ancestry or Deaths - USA - * Deaths Index - Ancestry` | Death | - | PDX |
| US state death index entry | `Deaths - USA - * Index - Ancestry or Deaths - USA - * Deaths Index - Ancestry` | Burial | - | PDX |
| US state death index entry | `Deaths - USA - * Index - Ancestry or Deaths - USA - * Deaths Index - Ancestry` | Occupation | - | PDX |
| US state death index entry | `Deaths - USA - * Index - Ancestry or Deaths - USA - * Deaths Index - Ancestry` | Birth | - | SDX\|SIX |
| Birth certificate, Irish birth register | `Birth Certificate - UK or Birth Register - Ireland - irishgenealogy.ie` | Birth | - | PDX |
| Birth certificate, Irish birth register | `Birth Certificate - UK or Birth Register - Ireland - irishgenealogy.ie` | Occupation | - | PDX |
| Birth certificate, Irish birth register | `Birth Certificate - UK or Birth Register - Ireland - irishgenealogy.ie` | Residence | - | PDX\|PIX |
| Birth certificate, Irish birth register | `Birth Certificate - UK or Birth Register - Ireland - irishgenealogy.ie` | family | - | PIX |
| Birth certificate, Irish birth register | `Birth Certificate - UK or Birth Register - Ireland - irishgenealogy.ie` | name | - | PIX |
| Marriage certificate, Irish marriage register | `Marriage Certificate - UK or Marriage Register - Ireland - irishgenealogy.ie` | Marriage | - | PDX |
| Marriage certificate, Irish marriage register | `Marriage Certificate - UK or Marriage Register - Ireland - irishgenealogy.ie` | family | - | PDX\|PIX |
| Marriage certificate, Irish marriage register | `Marriage Certificate - UK or Marriage Register - Ireland - irishgenealogy.ie` | Residence | - | PDX |
| Marriage certificate, Irish marriage register | `Marriage Certificate - UK or Marriage Register - Ireland - irishgenealogy.ie` | Occupation | - | PDX\|SDX |
| Marriage certificate, Irish marriage register | `Marriage Certificate - UK or Marriage Register - Ireland - irishgenealogy.ie` | Birth | - | SIX |
| Death certificate (UK), GRO digital image | `Death Certificate - UK or Death Register - UK - GRO Digital Images` | Death | - | PDX |
| Death certificate (UK), GRO digital image | `Death Certificate - UK or Death Register - UK - GRO Digital Images` | Residence | - | PDX\|SDX |
| Death certificate (UK), GRO digital image | `Death Certificate - UK or Death Register - UK - GRO Digital Images` | Occupation | - | SDX |
| Death certificate (UK), GRO digital image | `Death Certificate - UK or Death Register - UK - GRO Digital Images` | family | - | SDX |
| Death certificate (UK), GRO digital image | `Death Certificate - UK or Death Register - UK - GRO Digital Images` | Birth | - | SIX\|SDX |
| Death certificate (US state) | `Deaths - USA - * Certificates - Ancestry` | Death | - | PDX |
| Death certificate (US state) | `Deaths - USA - * Certificates - Ancestry` | Burial | - | PDX |
| Death certificate (US state) | `Deaths - USA - * Certificates - Ancestry` | Cremation | - | PDX |
| Death certificate (US state) | `Deaths - USA - * Certificates - Ancestry` | Birth | - | SDX |
| Death certificate (US state) | `Deaths - USA - * Certificates - Ancestry` | family | - | SDX |
| Death certificate (US state) | `Deaths - USA - * Certificates - Ancestry` | Residence | - | SDX\|PDX |
| Death certificate (US state) | `Deaths - USA - * Certificates - Ancestry` | Occupation | - | SDX |
| Hospital birth certificate (original held) | `Birth Certificate - China - *` | Birth | - | PDO |
| Notarial certificate of birth | `Notarial Certificate of Birth - *` | Birth | - | PDX |
| Notarial certificate of birth | `Notarial Certificate of Birth - *` | family | - | PDX |
| Baptism | `Baptisms - * or Parish Registers - *` | Christen | - | PD{O/X} |
| Baptism | `Baptisms - *` | Birth | - | PD{O/X} |
| Baptism | `Parish Registers - *` | Birth | SpecificItem~baptism\|baptised\|christened | PD{O/X} |
| Church marriage | `Church Marriages - * or Parish Registers - *` | Marriage | - | PD{O/X} |
| Church marriage | `Church Marriages - * or Parish Registers - *` | Marriage Bann | - | PD{O/X} |
| Church marriage | `Church Marriages - * or Parish Registers - *` | Marriage License | - | PD{O/X} |
| Church marriage | `Church Marriages - * or Parish Registers - *` | Occupation | SpecificItem~^marriage | PD{O/X}\|SD{O/X} |
| Church marriage | `Church Marriages - *` | Occupation | - | PD{O/X}\|SD{O/X} |
| Church marriage | `Church Marriages - * or Parish Registers - *` | Birth | SpecificItem~^marriage | SI{O/X} |
| Church marriage | `Church Marriages - *` | Birth | - | SI{O/X} |
| Burial | `Burials - * or Parish Registers - *` | Burial | - | PD{O/X} |
| Burial | `Burials - * or Parish Registers - *` | Death | - | PI{O/X}\|PD{O/X} |
| Burial | `Burials - * or Parish Registers - *` | Birth | SpecificItem~^burial\|age | SI{O/X} |
| Parish register, baptism, marriage or burial | `Baptisms - * or Church Marriages - * or Burials - * or Parish Registers - *` | family | - | PD{O/X} |
| Parish register, baptism, marriage or burial | `Baptisms - * or Church Marriages - * or Burials - * or Parish Registers - *` | Residence | - | PD{O/X} |
| Parish register, baptism | `Baptisms - * or Parish Registers - *` | Occupation | - | PD{O/X} |
| Parish register | `Baptisms - * or Parish Registers - *` | name | - | PD{O/X}\|PI{O/X} |
| US marriage licence docket | `Marriages - USA - * Marriage Records - Ancestry` | Marriage\|family\|Marriage License\|Residence\|Occupation | - | PDO |
| US marriage licence docket | `Marriages - USA - * Marriage Records - Ancestry` | Birth | - | SDO |
| Marriage index (other) | `Marriages - *` | Marriage | - | PDX\|PDO |
| Marriage index (other) | `Marriages - *` | family | - | PDX\|PDO |
| Marriage index (other) | `Marriages - *` | Birth | - | SIX\|SDO |
| Gravestone photograph (Find a Grave) | `Graves - International - Find a Grave` | Birth | SpecificItem~^photograph | SIO |
| Gravestone photograph (Find a Grave) | `Graves - International - Find a Grave` | Burial\|Death\|family | SpecificItem~^photograph | SDO |
| Memorial page (Find a Grave) | `Graves - International - Find a Grave` | Birth | - | SIX |
| Memorial page (Find a Grave) | `Graves - International - Find a Grave` | Burial\|Death\|family | - | SDX |
| Gravestone, memorial | `Graves - *` | Birth | - | SI{O/X} |
| Gravestone, memorial | `Graves - *` | Burial\|Death\|family | - | SD{O/X} |
| Census 1911, 1921 (household form); Irish census | `Census - England 1911 - * or Census - England 1921 - * or Census - Ireland * - *` | Residence\|Occupation\|name | - | PDO |
| Census 1911, 1921 (household form); Irish census | `Census - England 1911 - * or Census - England 1921 - * or Census - Ireland * - *` | Birth | - | SIO |
| Census 1911, 1921 (household form); Irish census | `Census - England 1911 - * or Census - England 1921 - * or Census - Ireland * - *` | Marriage | - | PIO |
| 1939 Register | `Register - England 1939 - *` | Residence\|Occupation\|name | - | PDX |
| 1939 Register | `Register - England 1939 - *` | Birth | - | SDX |
| 1939 Register | `Register - England 1939 - *` | Marriage | - | PIX |
| Census (enumerator's book), US, Scottish, index only | `Census - *` | Residence\|Occupation\|name | - | PDX |
| Census (enumerator's book), US, Scottish, index only | `Census - *` | Birth | - | SIX |
| Census (enumerator's book), US, Scottish, index only | `Census - *` | Marriage | - | PIX |
