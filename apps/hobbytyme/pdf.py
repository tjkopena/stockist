#!python3

from PyPDF2 import PdfReader

import re
import sys

import logberry

from dataclasses import dataclass

@dataclass
class LineItem:
    qty: int
    sku: str
    name: str
    price_retail: float
    price_wholesale: float
    mfg: str

manufacturer_codes = {
    "AER": "AeroTech",
    "EST": "Estes",
    "TAM": "Tamiya",
    "QST": "Quest",
    "EXL": "Excel",
    "VAL": "Vallejo",
}

if len(sys.argv) < 2:
    print("Must specify HobbyTyme invoice PDF file")
    exit(-1)

fn = sys.argv[1]

logberry.start()

def extract(fn: str):
    t = logberry.task("Extracting", file=fn)

    reader = PdfReader(fn)
    logberry.info("Pages", n=len(reader.pages))

    lineitems = []
    items = 0

    for page in reader.pages:
        text = page.extract_text()

        for line in text.splitlines():
            match = re.search(r"^\d+\s+(\d+)\s+(?:(?:EA)|(?:BX)|(?:PK))\s+(\w\w\w/\d+)\s+(.+)\s+([\d\.]+)\s+([\d\.]+)\s+(?:% )?([\d\.]+)\s+([\d\.]+)(?:\s\*)?\s*$",
                      line)

            if not match:
                continue

            qty = int(match.group(1))
            sku = match.group(2)
            name = str(match.group(3)).strip()

            price_retail = float(match.group(4))
            price_wholesale = float(match.group(6))

            mfg = sku[:3]
            mfg = manufacturer_codes.get(mfg, mfg)

            #logberry.info(f'"{name}";"{mfg}";"{sku}";"";"";{price_retail};{qty};{price_wholesale}')
            #print(f'{qty};"{mfg}";"{sku}";"";"{name}";{price_retail};{price_wholesale}')

            lineitems.append(LineItem(qty, sku, name, price_retail, price_wholesale, mfg))
            items += qty

    t.success(lineitems=len(lineitems), items=items)
    return lineitems

def write_csv(fn: str, items: list[LineItem]):
    fn += '.csv'
    t = logberry.task("Write CSV", fn=fn)
    with open(fn, "wt") as f:
        for item in items:
            f.write(f'"{item.sku}";{item.qty};{item.price_wholesale}\n')

            #print(f'{item.qty};"{item.mfg}";"{item.sku}";"";"{item.name}";{item.price_retail};{item.price_wholesale}')

    t.success()
try:

    items = extract(fn)
    write_csv(fn, items)

except Exception as e:
    logberry.exception(e)

logberry.stop()
