# Facts cited per record type (machine-readable)

Read by `scripts/citations/evaluate_links.py`. Draft (2026-10-28) from the "Facts cited per record
type" table in `rm-record-cleanup/source_standards.md` and the links of the records already cleaned
up; corrected by the user. Committed: no real names.

## Standards (copied 2026-10-28 from `rm-record-cleanup/source_standards.md`)

| # | Standard |
|---|---|
| G7 | Cite the record on each fact it supports, never on a record event. Record events are deleted once their date and place are on the facts; where the person has no such fact, the record event is changed into it |
| G8 | A person with no fact for what the record shows: the fact is created from the record |
| G9 | Dates known only from a registration quarter: "before" the month after the quarter (Jan-Mar 1904 -> Bef Apr 1904). Known only from a registration month: "before" the month after it |
| G17 | Cite on the event the record supports. A family citation only when the record itself shows the relationship (e.g. a certificate naming both partners or the parents); no citations on a person record as a whole |
| G22 | A Birth known only from an age: "between" the month after the event's month, age + 1 years earlier, and the event's month, age years earlier (age 25 on 30 Apr 1896 -> `DR+18700500..+18710400..`). Used when a new Birth fact is created from the age (G8); an existing Birth date is not changed |
| G23 | All evidence is cited on the event it bears on, even where it disagrees with the event; the disagreement goes to the issues at the end |
| G25 | Evidence from another record type is applied now under that type's standard; the citation's own clean-up waits for its record type |
| G37 | Any discrepancy between a cited record and the event it is cited on gets a note on the event giving what the record says |
| G38 | Census and 1939 Register as evidence of marriage: both partners at the same address, both shown married, no one else in the household married: the household citation is also cited on the couple's Marriage |
| G39 | Census and 1939 Register, couple with no Marriage fact: a G38 household with the couple as head and wife, both married: a Marriage is created for the family, dated "before" the earliest such census date, no place, with a note per census |

## Facts cited

A citation takes the first row whose Name matches its source's name and whose Condition holds.

- Name: source name patterns (`*` any text; " or " between patterns).
- Condition: `Field~regex` on a citation field (`Text` is the transcription), or `-`.
- Required: facts every citation must be linked to (fact type names; `family` a family link).
- Optional: facts the citation may be linked to. `Fact if Field~regex`: required when the
  condition holds. `name` an alternative name; `*` anything. A link to anything else is flagged.

| Record type | Name | Condition | Required | Optional |
|---|---|---|---|---|
| Birth index | `Birth Register - UK - FreeBMD or Birth Register - UK - GRO or Birth Register - Ireland - FamilySearch` | - | Birth | name |
| Marriage index | `Marriage Register - UK - FreeBMD` | - | Marriage | name |
| Death index | `Death Register - UK - FreeBMD or Death Register - UK - Ancestry or Death Register - UK Marine - Findmypast or Deaths - UK - *` | - | Death | Birth if SpecificItem~(age \|born ), name |
| US state death index | `Deaths - USA - * Index - Ancestry or Deaths - USA - * Deaths Index - Ancestry` | - | Death | Birth, Burial, Occupation |
| Birth certificate, Irish birth register | `Birth Certificate - UK or Birth Register - Ireland - irishgenealogy.ie` | - | Birth, family | Occupation, Residence, name |
| Hospital birth certificate | `Birth Certificate - China - *` | - | Birth | |
| Notarial certificate of birth | `Notarial Certificate of Birth - *` | - | Birth, family | |
| Marriage certificate, Irish marriage register | `Marriage Certificate - UK or Marriage Register - Ireland - irishgenealogy.ie` | - | Marriage, family | Birth, Occupation, Residence, name |
| Death certificate (UK), GRO digital image | `Death Certificate - UK or Death Register - UK - GRO Digital Images` | - | Death | Birth, Occupation, Residence, family, name |
| Death certificate (US state) | `Deaths - USA - * Certificates - Ancestry` | - | Death | Birth, Burial, Cremation, Occupation, Residence, family |
| Banns | `Church Marriages - * or Parish Registers - *` | SpecificItem~^banns | Marriage Bann | family, name |
| Church marriage | `Church Marriages - *` | - | Marriage, family | Birth, Occupation, Residence, Marriage Bann, Marriage License, name |
| Parish register baptism | `Parish Registers - *` | SpecificItem~^baptism\|baptised\|christened | Christen, family | Birth, Occupation, Residence, name |
| Parish register marriage | `Parish Registers - *` | SpecificItem~^marriage\|married | Marriage, family | Birth, Occupation, Residence, Marriage Bann, name |
| Parish register burial | `Parish Registers - *` | SpecificItem~^burial\|buried | Burial | Death, Birth, Residence, family |
| Baptism | `Baptisms - *` | - | Christen, family | Birth, Occupation, Residence, name |
| Burial | `Burials - *` | - | Burial | Death, Birth, Residence, family |
| Marriage index or register (other) | `Marriages - *` | - | Marriage, family | Birth, Occupation, Residence, Marriage License |
| Gravestone, memorial | `Graves - *` | - | Burial, Death | Birth, family |
| Census 1811 (headcount, no ages) | `Census - England 1811 *` | - | Residence | name |
| Census, 1939 Register | `Census - * or Register - England 1939 - *` | - | Residence, Birth | Occupation, Marriage, name |
| Oral history | `Oral history - *` | - | | * |
