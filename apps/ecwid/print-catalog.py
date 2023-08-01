
if __name__ != '__main__':
    raise Error("This is a script, not intended to be imported")

from stockist import ecwid

import logberry
import tjawn

logberry.start()

fn_categories = 'data/ecwid_categories.jawn'
fn_catalog = 'data/ecwid_catalog.jawn'

t = logberry.task("Read categories", file=fn_categories)
categories = { c.id: c for c in ecwid.as_categories(tjawn.loads(open(fn_categories, "rt").read())) }
t.success()

t = logberry.task("Read catalog", file=fn_catalog)
products = ecwid.as_products(tjawn.loads(open(fn_catalog, "rt").read()))
t.success()

logberry.stop()


#catalog = [['sku', 'name', 'price', 'msrp', 'cost']]
#for p in products:
#    catalog.append([p.sku, p.name, p.price, p.msrp, p.cost])

print()
for p in products:
    defcat = categories.get(p.defaultCategory, None)
    if defcat:
        defcat = defcat.name

    print(f"{str(p.sku):<16} {str(p.name):<40} {str(p.quantity):<3} ${str(p.price):<8} ${str(p.msrp):<8} ${str(p.cost):<8} {defcat}")
