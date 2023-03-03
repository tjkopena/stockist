
if __name__ != '__main__':
    raise Error("This is a script, not intended to be imported")

from stockist import ecwid
from stockist import sheets

import logberry
import tjawn

import sys

logberry.start()

if len(sys.argv) < 2:
    print("Must specify invoice label")
    exit(-1)

invoice = sys.argv[1]

api = sheets.API(sheets.load_configuration())
items = api.download_invoice(invoice)

fn = f"{invoice.replace(' ', '-')}.jawn"
t = logberry.task("Writing invoice to file", file=fn)
with open(fn, "wt") as f:
    f.write(tjawn.dumps(items))
t.success()

logberry.stop()
