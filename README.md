# Stockist

## Usage

## Ecwid

Settings in `.conf/ecwid.jawn`:
```
store: <store id>
token: <private token>
```

Download catalog
```
python -m apps.ecwid.get-catalog
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

## Development

### Dependencies

* squareup
* tjawn
* logberry
* dacite
* dataclasses_json
* requests
* gspread
