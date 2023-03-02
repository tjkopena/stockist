
import logberry
import tjawn

from typing import Optional
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, Undefined
from dacite import from_dict

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


@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class Product:
    id: str
    sku: str
    name: Optional[str] = None
    price: Optional[float] = None
    msrp: Optional[float] = field(metadata=config(field_name="compareToPrice"), default=None)
    cost: Optional[float] = field(metadata=config(field_name="costPrice"), default=None)

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


def client(settings: Settings):
    return Client(settings)

def as_products(products):
    return [Product.from_dict(p) for p in products]
