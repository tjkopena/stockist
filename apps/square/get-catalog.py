
if __name__ != '__main__':
    raise Error("This is a script, not intended to be imported")

from datetime import datetime
import os
from os import path

from stockist import square

import logberry
import tjawn

logberry.start()

output = 'square_catalog.jawn'

if path.exists(output):
    t = logberry.task("Archiving prior export")
    newout = "square_catalog-" + datetime.fromtimestamp(path.getmtime(output)).strftime("%Y%m%d") + ".jawn"
    os.rename(output, newout)
    t.success(archive=newout)

api = square.client(square.load_configuration())
products = api.get_catalog()

t = logberry.task("Write catalog", file=output)
with open(output, "wt") as f:
    f.write(tjawn.dumps(products))
t.success()

logberry.stop()
