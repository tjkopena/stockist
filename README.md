# Stockist

## Usage
logberry
pip install -e /home/joe/code/logberrypy/

tjawn
pip install -e /home/joe/code/tjawn/src/py

dataclasses_json
dacite
requests
pypdf2
gspread

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

Summarize purchase orders into a workbook, default `data/YYYYMMDD.xlsx`;
raw downloads are saved to `data/brickowl-orders-YYYYMMDD.jawn`
```
python -m apps.brickowl.orders
python -m apps.brickowl.orders --start 2026-10-01 --end 20261026
python -m apps.brickowl.orders --orders 4657373,8853584 \
       --output data/bricks.xlsx
```

Non-USD orders are converted at the rate actually paid if paid in USD,
otherwise at the ECB reference rate (frankfurter.dev) for the order
date.

## Development

### Dependencies

* squareup
* dacite
* dataclasses_json
* requests
* gspread

* tjawn
* logberry



## Use


Delete the Square catalog before updating Ecwid stock!
