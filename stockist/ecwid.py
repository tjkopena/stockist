
import logberry
import tjawn

from typing import Optional
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, Undefined
from dacite import from_dict, Config

import json
import requests

@dataclass
class Settings:
    store: str
    token: str

def load_configuration(fn='.conf/ecwid.jawn'):
    return from_dict(data_class=Settings, data=tjawn.loads(open(fn, "rt").read()))


@dataclass
class Results:
    total: int
    count: int
    offset: int
    limit: int
    items: list

    def __str__(self):
        return f"Results {{total {self.total}, offset {self.offset}, count {self.count}, limit {self.limit}}}"

def dict_remap(d, fields):
    for k in fields:
        if k[0] in d:
            d[k[1]] = d.pop(k[0])
    return d

@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class Product:
    id: int
    sku: str
    name: Optional[str] = None
    price: Optional[float] = None
    msrp: Optional[float] = None
    cost: Optional[float] = None

    @staticmethod
    def _remap(d):
        return dict_remap(d, [
            ('compareToPrice', 'msrp'),
            ('costPrice', 'cost')
            ])

    def __str__(self):
        s = f"[{self.sku}]"
        s += f" {self.name}" if self.name else ""

        s += f" (${self.price if self.price else '--'} : ${self.msrp if self.msrp else '--'} : ${self.cost if self.cost else '--'})"

        return s


class Client:
    def __init__(self, settings: Settings):
        self.store = settings.store
        self.token = settings.token

    def get_catalog(self):
        t = logberry.task("Retrieving catalog")

        products = []
        total = -1
        offset = 0

        while total < 0 or len(products) < total:
            tt = t.task("Products request", offset=offset)
            res = requests.get(f"https://app.ecwid.com/api/v3/{self.store}/products",
                               {'offset': offset},
                               headers = {
                                   'Authorization': f"Bearer {self.token}",
                                   'Accept': 'application/json',
                               })
            res.raise_for_status()
            tt.success()

            results = Results(**res.json())

            offset = offset + results.count
            total = results.total
            products.extend(results.items)

        t.success(items=len(products))

        return products

    def update_qty(self, product, quantity):
        t = logberry.task("Update quantity", sku=product.sku, qty=quantity)
        res = requests.put(f"https://app.ecwid.com/api/v3/{self.store}/products/{product.id}/inventory",
                       json = {
                           'quantityDelta': quantity,
                           },
                       headers = {
                           'Authorization': f"Bearer {self.token}",
                           'Accept': 'application/json',
                       })
        res.raise_for_status()
        t.success()

def client(settings: Settings):
    return Client(settings)

def as_products(products):
    return [from_dict(data_class=Product, data=Product._remap(p), config=Config(type_hooks={int: int})) for p in products]
