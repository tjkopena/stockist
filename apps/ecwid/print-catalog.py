
if __name__ != '__main__':
    raise Error("This is a script, not intended to be imported")

from stockist import ecwid

import logberry
import tjawn

logberry.start()

input = 'ecwid_catalog.jawn'

t = logberry.task("Read catalog", file=input)
products = ecwid.as_products(tjawn.loads(open(input, "rt").read()))
t.success()

logberry.stop()


#catalog = [['sku', 'name', 'price', 'msrp', 'cost']]
#for p in products:
#    catalog.append([p.sku, p.name, p.price, p.msrp, p.cost])

print()
for p in products:
    print(f"{str(p.sku):<16} {str(p.name):<32} {str(p.price):<8} {str(p.msrp):<8} {str(p.cost):<8}")
