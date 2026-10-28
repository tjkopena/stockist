#!python3

from PyPDF2 import PdfReader

import sys

import logberry

if len(sys.argv) < 2:
    print("Must specify Estes invoice PDF file")
    exit(-1)

fn = sys.argv[1]

logberry.start()

def extract(fn: str):
    t = logberry.task("Extracting", file=fn)

    reader = PdfReader(fn)
    logberry.info("Pages", n=len(reader.pages))

    lineitems = []
    items = 0

    for page in reader.pages:
        text = page.extract_text()

        for line in text.splitlines():
            print(line)


    t.end_success(lineitems=len(lineitems), items=items)
    return lineitems

try:

    extract(fn)

except Exception as e:
    logberry.end_exception(e)

logberry.stop()
