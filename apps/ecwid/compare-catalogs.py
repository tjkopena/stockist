
if __name__ != '__main__':
    raise Error("This is a script, not intended to be imported")

from stockist import ecwid

import sys

import logberry
import tjawn

if len(sys.argv) < 3:
    print("Must specify two catalog files")
    exit(-1)

logberry.start()

fn_a = sys.argv[1]
fn_b = sys.argv[2]

fn_catalog = 'data/ecwid_catalog.jawn'

t = logberry.task("Read catalog a", file=fn_a)
prod_a = ecwid.as_products(tjawn.loads(open(fn_a, "rt").read()))
t.end_success()

t = logberry.task("Read catalog b", file=fn_b)
prod_b = ecwid.as_products(tjawn.loads(open(fn_b, "rt").read()))
t.end_success()


prod_a = {x.sku:x for x in prod_a}
prod_b = {x.sku:x for x in prod_b}

logberry.stop()

for b in prod_b.values():
    if not b.sku in prod_a:
        print(f"Not in A: {b.sku}")

for a in prod_a.values():
    if not a.sku in prod_b:
        print(f"Not in B: {a.sku}")


for b in prod_b.values():
    if b.sku not in prod_a:
        continue

    a = prod_a[b.sku]

    if b != a:
        print(b.sku)
        print(f"  {a}")
        print(f"  {b}")
