# Stockist

## Usage
logberry
pip install -e /home/joe/code/logberrypy/

dataclasses_json
dacite
requests
pypdf2
gspread
tjawn>=2.0

square?

### Ecwid

Settings in `.conf/ecwid.jawn`:
```
store: <store id>
token: <private token>
```

Download catalog
```
python -m apps.ecwid.get-catalog


python -m apps.ecwid.get-categories
```

Print catalog
```
python -m apps.ecwid.print-catalog
```

### Square

Settings in `.conf/square.jawn`:
```
access_token: <acess token>
environment: <production or sandbox>
```

Download catalog
```
python -m apps.square.get-catalog
```

Delete catalog
```
python -m apps.square.delete-catalog
```

Create manual import sheet
```
python -m apps.square.gen-import
```

### Google Sheets

Settings in `.conf/sheets.jawn`:
```
credentials: <filename for JSON from Google Sheets>
authorization: <filename were authorization token is/will be saved>
workbook_id: <ID for workbook to use>

catalog_sheet: <optional tab label for worksheet to use as catalog>
```

Upload catalog
```
python -m apps.sheets.upload-catalog
```

Download invoice worksheet
```
python -m apps.sheets.download-invoice <invoice sheet label>
```

Update stock
```
python -m apps.sheets.update-stock <invoice filename or sheet label>
```

### HobbyTyme

```
python -m apps.hobbytyme.pdf /tmp/mozilla_joe0/01019940.pdf

python -m apps.sheets.download-invoice 'HobbyTyme 20230517'

python -m apps.sheets.update-stock 'HobbyTyme 20230517'
```

### Estes

```
python -m apps.estes.pdf /tmp/mozilla_joe0/01019940.pdf

```

### Brick Owl

Settings in `.conf/brickowl.jawn`:
```
api_key: <API key>
```

Download purchase orders into the local cache, one `<order ID>.jawn`
file each in `data/brickowl/orders/` (`--cache` or `cache:` in
`.conf/brickowl.jawn` to change); all orders if no `--orders`,
`--from`, or `--in` scope is given
```
python -m apps.brickowl.get-orders
python -m apps.brickowl.get-orders --in 2026-10-01::2026-10-26
python -m apps.brickowl.get-orders --from 4657373 --orders 8853584
```

Orders already cached are only downloaded again if Brick Owl reports
them updated since they were last confirmed current, as recorded in
`.get-orders.jawn` in the cache folder (`--cache-log` or `cache_log:` to
change); `--force` downloads every order in scope regardless, e.g., to
refresh Natural IDs
```
python -m apps.brickowl.get-orders --force
```

List cached orders in scope; `--csv` for CSV, `--sort` to order by
`id`, `time`, `date`, `store`, `status`, or `total`, each optionally
`:asc` or `:desc` (default `time,id`, newest first)
```
python -m apps.brickowl.list-orders
python -m apps.brickowl.list-orders --status shipped+ --sort store,total
python -m apps.brickowl.list-orders --in 2026-01-01:: --csv
```

Summarize cached orders in scope into an XLSX workbook, a summary sheet
of all items purchased then a sheet per order; written to
`data/brickowl/orders.xlsx` unless `--out` (or `out:` in
`.conf/brickowl.jawn`) is given; summary items are shown with their
25px image from the image cache (see `get-images` below, `--images` to
change), any missing are warned of and left blank
```
python -m apps.brickowl.summarize-orders
python -m apps.brickowl.summarize-orders --in 2026-10-01:: --out data/october.xlsx
```

Download small item images for cached orders in scope as
`<BOID>.75px.png` plus a downsampled `<BOID>.25px.png` in
`data/brickowl/images/` (`--images` or `images:` in
`.conf/brickowl.jawn` to change); images already present are skipped,
and a missing 25px image is regenerated from the 75px one
```
python -m apps.brickowl.get-images
python -m apps.brickowl.get-images --in 2026-10-01::
```

Scope directives may also be set in `.conf/brickowl.jawn`, each a
string or list of strings as on the command line; they are ignored if
any scope directive is given on the command line
```
status: "Shipped+"
in: ["2025-01-01::2025-06-30", "2026-01-01::"]
```


## Development

### Dependencies

* squareup
* dacite
* dataclasses_json
* requests
* gspread

* tjawn (>= 2.0)
* logberry
* wcwidth
* Pillow



## Use


Delete the Square catalog before updating Ecwid stock!
