"""Shared fixture for the evaluate_links/quality/record_events/places/scans tests: invented records."""

from rmutils import fields_blob
from support import ScriptTestCase

EXTRA_SQL = """
CREATE TABLE SourceTable (SourceID INTEGER PRIMARY KEY, Name TEXT, TemplateID INTEGER, Fields BLOB);
CREATE TABLE CitationTable (CitationID INTEGER PRIMARY KEY, SourceID INTEGER, Fields BLOB, ActualText TEXT);
CREATE TABLE MultimediaTable (MediaID INTEGER PRIMARY KEY, MediaType INTEGER, MediaPath TEXT, MediaFile TEXT,
    Caption TEXT, RefNumber TEXT, Description TEXT, Date TEXT);
INSERT INTO FactTypeTable VALUES (1, 0, 'Birth'), (2, 0, 'Death'), (4, 0, 'Burial'), (29, 0, 'Residence'),
    (300, 1, 'Marriage'), (1035, 0, 'Directory'), (1048, 0, 'Newspaper Article'), (1028, 0, 'Marriage Register - UK');
INSERT INTO PersonTable (PersonID, Sex) VALUES (1, 0), (2, 1), (3, 0);
INSERT INTO NameTable (NameID, OwnerID, Given, Surname, IsPrimary) VALUES (1, 1, 'John', 'Doe', 1),
    (2, 2, 'Mary', 'Doe', 1), (3, 3, 'Tom', 'Doe', 1);
INSERT INTO FamilyTable (FamilyID, FatherID, MotherID) VALUES (7, 1, 2);
INSERT INTO PlaceTable (PlaceID, PlaceType, Name, MasterID) VALUES (1, 0, 'Testham, Kent, England', 0),
    (2, 2, '12 High Street', 1), (3, 2, '12, High Street', 1), (4, 0, '5 Mill Lane, Testham', 0), (5, 2, 'Orphan', 99),
    (6, 0, 'Otherton, Kent, England', 0);
INSERT INTO EventTable (EventID, EventType, OwnerType, OwnerID, PlaceID, SiteID, Date, IsPrimary, Details, Note) VALUES
    (10, 1, 0, 1, 1, 2, 'D.+18500101..+00000000..', 1, '', ''),
    (11, 2, 0, 1, 0, 0, 'D.+19100000..+00000000..', 1, '', ''),
    (12, 1, 0, 3, 6, 2, '.', 1, 'at 4 Church Street', ''),
    (13, 29, 0, 1, 1, 0, 'D.+18810403..+00000000..', 1, '', ''),
    (14, 1035, 0, 1, 1, 3, 'D.+18810403..+00000000..', 0, 'grocer', ''),
    (15, 1035, 0, 3, 1, 0, 'D.+19000000..+00000000..', 0, '', ''),
    (16, 1048, 0, 1, 0, 0, '.', 0, '', ''),
    (17, 300, 1, 7, 0, 0, 'D.+18750000..+00000000..', 1, '', ''),
    (18, 1028, 0, 2, 0, 0, 'D.+18750000..+00000000..', 0, '', ''),
    (19, 29, 0, 1, 1, 0, 'D.+18810403..+00000000..', 0, '', '');
"""


class EvaluateTestCase(ScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.use_full_schema(EXTRA_SQL)
        self.table = self.tmp / "table.md"

    def add(self, sql: str, rows: list[tuple]) -> None:
        import sqlite3
        conn = sqlite3.connect(self.db)
        conn.executemany(sql, rows)
        conn.commit()
        conn.close()

    def citations(self) -> None:
        """Sources 1 (index, no images), 2 (images), 3 (unmatched); citations 20-24 with links."""
        web = fields_blob({"Descriptor": "database"}, declaration=False)
        images = fields_blob({"Descriptor": "database with images"}, declaration=False)
        self.add("INSERT INTO SourceTable VALUES (?, ?, ?, ?)", [
            (1, "Birth Register - UK - TestBMD", 6, web), (2, "Burials - England - Testham - Ancestry", 6, images),
            (3, "Notes", 0, b"")])
        item = lambda text: fields_blob({"SpecificItem": text}, declaration=False)
        self.add("INSERT INTO CitationTable VALUES (?, ?, ?, ?)", [
            (20, 1, item("entry for John Doe"), ""), (21, 1, item("entry for Tom Doe, age 5"), ""),
            (22, 2, item("burial of John Doe"), ""), (23, 3, b"", ""), (24, 1, item("entry for John Doe"), "")])
        self.add("INSERT INTO CitationLinkTable (LinkID, CitationID, OwnerType, OwnerID, Quality) VALUES (?, ?, ?, ?, ?)", [
            (1, 20, 2, 10, "PIX"), (2, 21, 2, 12, "~~~"), (3, 21, 0, 3, "PIX"), (4, 22, 2, 11, "PDX"),
            (5, 22, 2, 16, "PDO"), (6, 23, 2, 13, "PDX"), (7, 24, 2, 11, "PIX"), (8, 20, 2, 14, "PIX")])
