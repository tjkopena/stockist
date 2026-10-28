#!python3

import re
import sys

import logberry

manufacturer_codes = {
    "AER": "AeroTech",
    "EST": "Estes",
    "TAM": "Tamiya",
    "QST": "Quest",
    "EXL": "Excel",
    "VAL": "Vallejo",
}

logberry.start()

if len(sys.argv) < 2:
    logberry.fail("Must specify order invoice text")
    exit(-1)

fn = sys.argv[1]

def process(fn: str):
    t = logberry.task("Extracting", file=fn)
    with open(fn, "rt") as f:
        count = 1
        for line in f:
            match = re.search(r"^\d+ (\d+) (?:(?:EA)|(?:BX)|(?:PK)) (\w\w\w/\d+) (.+) ([\d\.]+) ([\d\.]+) (?:% )?([\d\.]+) ([\d\.]+)(?:\s\*)?\s*$",
                              line)
            if not match:
                raise ValueError(f"Could not parse line {count}: `{line}`")

            qty = match.group(1)
            sku = match.group(2)
            name = match.group(3)

            price_retail = match.group(4)
            price_wholesale = match.group(6)

            manf = sku[:3]
            manf = manufacturer_codes.get(manf, manf)

            #print(f'"{name}";"{manf}";"{sku}";"";"";{price_retail};{qty};{price_wholesale}')
            #print(f'{qty};"{manf}";"{sku}";"";"{name}";{price_retail};{price_wholesale}')
            print(f'"{sku}";{qty};{price_wholesale}')
            count += 1
    t.end_success()



#print('"name";"mfg";"sku";"";"";price_retail;qty;price_wholesale')

try:
    process(fn)
except Exception as e:
    logberry.end_exception(e)

logberry.stop()
