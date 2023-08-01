
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


#catalog = [['sku', 'name', 'price', 'msrp', 'cost']]
#for p in products:
#    catalog.append([p.sku, p.name, p.price, p.msrp, p.cost])

#@dataclass
#class Item:
#    name: str
#    sku: str
#    category: str
#    price: float
#    quantity: int

fn = "data/square-import.csv"
t = logberry.task("Write import", file=fn)
with open(fn, "wt") as f:
    f.write('"Item Name","Description","SKU","Variation Name","Category","Square Online Item Visibility","Price","New Quantity","Tax - PA Sales Tax (6%)"\n')
    for p in products:
        defcat = categories.get(p.defaultCategory, None)
        category = "Get Started!" if 144928242 in p.categories else defcat.name if defcat else "Model Rockets"

        name = p.name.replace('"', '\'')
        f.write(f'"{name}","","{str(p.sku)}","","{category}",visible,{p.price},{p.quantity},Y\n')
t.success(items=len(products))

                ## Token
# Item Name
                ## Variation Name
# SKU
                ## Description
# Category
# Square Online Item Visibility
# Price
                ## Sellable
                ## Stockable
                ## Option Name 1
                ## Option Value 1
# Current Quantity Rocketship Games
                ## New Quantity Rocketship Games
                ## Stock Alert Enabled Rocketship Games
                ## Stock Alert Count Rocketship Games
# Tax - PA Sales Tax (6%)

logberry.stop()
