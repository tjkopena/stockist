
if __name__ != '__main__':
    raise Error("This is a script, not intended to be imported")

from stockist import ecwid
from stockist import sheets

import logberry
import tjawn

logberry.start()

input = 'ecwid_catalog.jawn'

t = logberry.task("Read catalog", file=input)
products = ecwid.as_products(tjawn.loads(open(input, "rt").read()))
t.success()

api = sheets.API(sheets.load_configuration())
api.update_catalog(products)

logberry.stop()
