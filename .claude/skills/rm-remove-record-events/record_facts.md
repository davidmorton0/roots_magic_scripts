# Record facts and the facts they become (machine-readable)

Read by `scripts/people/evaluate_record_events.py`. A record fact (FactTypeID 1000 and over, e.g.
"Census England 1881") is a fact made for one record. G7: the record is cited on the facts it
supports instead; record events are deleted once their date, place and citations are on those
facts; where the person has no such fact, the record event is changed into it. Draft (2026-10-28)
from the "Facts cited per record type" table in `rm-record-cleanup/source_standards.md`; corrected
by the user.

## Record facts

- Record fact: the record fact's name (`*` any text; " or " between patterns).
- Main fact: the fact type it becomes; `-` not decided yet (each event is flagged for a decision).
- Match: which of the person's facts of that type it is the same as: `primary` (the primary one,
  else the first), `date` (the one with the same date: one per census or register year).

| Record fact | Main fact | Match |
|---|---|---|
| `Census * or Register UK 1939` | Residence | date |
| `Birth Certificate - UK or Child Birth Cert UK or Birth Register - UK or Birth Register Ireland` | Birth | primary |
| `Marriage Certificate - UK or Marriage Register - UK or Marriage - Church - UK or Marriage - Civil` | Marriage | primary |
| `Death Certificate - UK or Death Register or Death Certificate - US` | Death | primary |
| `Grave` | Burial | primary |
| `Directory or Electoral Register` | Residence | date |
| `Will - Administration` | Probate | primary |
| `WW1 Service or WW1 Draft or WW2 Draft or WW1 Wounded` | Military | date |
| `School Admission` | Education | date |
| `Marriage Witness - UK` | - | - |
| `Travel or Passport Application or Prison or Ulster Declaration or Tax Records or General or Research Notes or Newspaper Article` | - | - |
