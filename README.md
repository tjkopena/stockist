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

```
python -m apps.square.delete-catalog
```

## Development

### Dependencies

* squareup
* tjawn
* logberry
* dacite
* dataclasses_json
* requests
