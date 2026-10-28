#!python3

import re
import sys

import logberry

from dataclasses import dataclass

@dataclass
class LineItem:
    qty: int
    sku: str
    name: str
    price_wholesale: float

if len(sys.argv) < 2:
    logberry.fail("Must specify order invoice text")
    exit(-1)

fn = sys.argv[1]

logberry.start()

def process(fn: str):
    t = logberry.task("Extracting", file=fn)
    lineitems=[]
    count = 0
    with open(fn, "rt") as f:
        loc = 1
        for line in f:
            match = re.search(r"^(?P<name>.+)\s+SKU: (?P<sku>\d+)\s+(?P<qty>\d+)\s+(?P<cost>\$?[\d\.]+)\s+\$[\d\.]+\s+\$[\d\.]+$",
                              line)
            if not match:
                raise ValueError(f"Could not parse line {loc}: `{line}`")

            name = match.group("name")
            sku = int(match.group("sku"))
            qty = int(match.group("qty"))
            price_wholesale = float(match.group("cost"))

            lineitems.append(LineItem(qty, sku, name, price_wholesale))
            count += 1
            loc += 1

    t.end_success(lineitems=len(lineitems), count=count)
    return lineitems

def write_csv(fn: str, items: list[LineItem]):
    fn += '.csv'
    t = logberry.task("Write CSV", fn=fn)
    with open(fn, "wt") as f:
        for item in items:
            f.write(f'"EST/{item.sku}";{item.qty};{item.price_wholesale}\n')
    t.end_success()

try:
    items = process(fn)
    write_csv(fn, items)
except Exception as e:
    logberry.exception(e)

logberry.stop()
