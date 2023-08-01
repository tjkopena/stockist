
if __name__ != '__main__':
    raise Error("This is a script, not intended to be imported")

from stockist import ecwid
from stockist import sheets

import logberry
import tjawn

from os import path

import sys

logberry.start()

t = logberry.task("Read catalog", file='data/ecwid_catalog.jawn')
catalog = ecwid.as_products(tjawn.loads(open('data/ecwid_catalog.jawn', "rt").read()))
t.success()

api = ecwid.client(ecwid.load_configuration())
for p in catalog:
    api.update_unlimited(p)

logberry.stop()
