
if __name__ != '__main__':
    raise Error("This is a script, not intended to be imported")

from datetime import datetime
import os
from os import path

from stockist import ecwid

import logberry
import tjawn

logberry.start()

output = 'data/ecwid_categories.jawn'

if path.exists(output):
    t = logberry.task("Archiving prior export")
    newout = "data/ecwid_categories-" + datetime.fromtimestamp(path.getmtime(output)).strftime("%Y%m%d") + ".jawn"
    os.rename(output, newout)
    t.success(archive=newout)

api = ecwid.client(ecwid.load_configuration())
categories = api.get_categories()

t = logberry.task("Write categories", file=output)
with open(output, "wt") as f:
    f.write(tjawn.dumps(categories))
t.success()

logberry.stop()
