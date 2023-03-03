
import logberry
import tjawn

from dataclasses import dataclass
from dacite import from_dict, Config

import gspread

@dataclass
class Settings:
    credentials: str
    authorization: str
    workbook_id: str
    catalog_sheet: str = 'Catalog'

@dataclass
class InvoiceItem:
    sku: str
    quantity: int
    wholesale: float
    name: str

    def __str__(self):
        return f"{self.sku:<9} {self.quantity:>2} {self.name}"

def load_configuration(fn='.conf/sheets.jawn'):
    return from_dict(data_class=Settings, data=tjawn.loads(open(fn, 'rt').read()))

class API:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._catalog_sheet = None

        t = logberry.task("Connecting to Google Sheets")
        self.gc = gspread.oauth(credentials_filename=settings.credentials,
                                authorized_user_filename=settings.authorization)

        self.workbook = self.gc.open_by_key(settings.workbook_id)
        t.success()

    @property
    def catalog_sheet(self):
        if not self._catalog_sheet:
            self._catalog_sheet = self.workbook.worksheet(self.settings.catalog_sheet)
        return self._catalog_sheet

    def update_catalog(self, products):
        t = logberry.task("Updating catalog sheet", n=len(products))

        catalog = [['sku', 'name', 'price', 'msrp', 'cost']]
        for p in products:
            catalog.append([p.sku, p.name, p.price, p.msrp, p.cost])

        self.catalog_sheet.clear()
        self.catalog_sheet.update('A1', catalog)

        t.success()

    def download_invoice(self, invoice):
        t = logberry.task("Retrieving invoice", invoice=invoice)
        sheet = self.workbook.worksheet(invoice)
        items = [InvoiceItem(i[0], int(i[1]), float(i[2].removeprefix('$')), i[3]) for i in sheet.get("B4:E")]
        t.success()

        return items

def as_invoiceitems(items):
    return [from_dict(data_class=InvoiceItem, data=i, config=Config(type_hooks={int: int})) for i in items]
