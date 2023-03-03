
if __name__ != '__main__':
    raise Error("This is a script, not intended to be imported")

from stockist import ecwid
from stockist import sheets

import logberry
import tjawn

from os import path

import sys

logberry.start()

if len(sys.argv) < 2:
    print("Must specify invoice filename or sheet label")
    exit(-1)

fn = sys.argv[1]

if not path.exists(fn):
    fn = f"{fn.replace(' ', '-')}.jawn"
    if not path.exists(fn):
        print("Cannot find invoice for '{sys.argv[1]}'")
        exit(-1)


t = logberry.task("Reading invoice", file=fn)
items = sheets.as_invoiceitems(tjawn.loads(open(fn, "rt").read()))
t.success()

t = logberry.task("Read catalog", file='ecwid_catalog.jawn')
catalog = ecwid.as_products(tjawn.loads(open('ecwid_catalog.jawn', "rt").read()))
t.success()

catalog = { p.sku: p for p in catalog}

api = ecwid.client(ecwid.load_configuration())
for i in items:
    p = catalog.get(i.sku, None)
    if not p:
        raise ValueError("Invoice item SKU not in catalog", i.sku)
    api.update_qty(p, i.quantity)

logberry.stop()
