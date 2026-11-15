
import logberry
import tjawn

from typing import Optional, Final
from dataclasses import dataclass
from dacite import from_dict

from datetime import datetime, date, time, timezone
import html
import math
import re
import requests
import unicodedata


BRICKOWL: Final[str] = 'brickowl'

API_URL: Final[str] = 'https://api.brickowl.com/v1'
RATES_URL: Final[str] = 'https://api.frankfurter.dev/v1'
USER_AGENT: Final[str] = 'stockist-brickowl/1.0'

STATUSES: Final[tuple] = ('Pending', 'Payment Submitted', 'Payment Received',
                          'Processing', 'Processed', 'Shipped', 'Received',
                          'On Hold', 'Cancelled')
STATUS_RECEIVED: Final[str] = '6'
STATUS_ON_HOLD: Final[str] = '7'
STATUS_CANCELLED: Final[str] = '8'

# Monetary fields of order views and items, by the currency they are in.
BASE_CURRENCY_FIELDS: Final[tuple] = ('ship_total', 'eu_duty', 'base_order_total', 'sub_total',
                                      'final_sub_total_excluding_tax', 'coupon_discount',
                                      'tax_amount', 'refund_shipping', 'refund_eu_duty',
                                      'refund_adjustment', 'refund_subtotal', 'refund_total')
PAYMENT_CURRENCY_FIELDS: Final[tuple] = ('payment_total',)
ITEM_CURRENCY_FIELDS: Final[tuple] = ('base_price',)
USD_SUFFIX: Final[str] = '_USD'

DEFAULT_CONF: Final[str] = '.conf/brickowl.jawn'
DEFAULT_CACHE: Final[str] = 'data/brickowl/orders'


DATE_FORMATS: Final[tuple] = ('%Y%m%d', '%Y-%m-%d', '%Y/%m/%d')

# Plain decimal number, as monetary fields are given.
NUMBER: Final = re.compile(r'[+-]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][+-]?[0-9]+)?')


class APIError(Exception):
    pass


def parse_date(s):
    """Local calendar date of a YYYYMMDD, YYYY-MM-DD, or YYYY/MM/DD date."""
    if re.fullmatch(r'[0-9]{8}|[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{4}/[0-9]{2}/[0-9]{2}', s):
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                pass
    raise ValueError(f"Invalid date '{s}', must be YYYYMMDD, YYYY-MM-DD, or YYYY/MM/DD")

def local_day_start(d: date):
    """Unix timestamp (UTC) of the local midnight beginning date d."""
    return int(datetime.combine(d, time()).timestamp())

def local_time(ts):
    """Local system time of a Unix timestamp, for display."""
    return datetime.fromtimestamp(ts, timezone.utc).astimezone()


@dataclass
class Settings:
    api_key: Optional[str] = None
    cache: str = DEFAULT_CACHE

def read_configuration(fn=DEFAULT_CONF):
    """Raw configuration file contents."""
    data = tjawn.loadf(fn)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"Configuration file '{fn}' is not a map")
    return data

def settings_from(data):
    return from_dict(data_class=Settings, data=data)


class Client:
    def __init__(self, settings: Settings):
        self.key = settings.api_key

    def _get(self, endpoint, **params):
        t = logberry.task("Brick Owl request", endpoint=endpoint, **params)
        res = requests.get(f"{API_URL}/{endpoint}",
                           {'key': self.key, **params},
                           headers = {
                               'User-Agent': USER_AGENT,
                               'Accept': 'application/json',
                           })
        if not res.ok:
            try:
                msg = res.json()['error']
            except Exception:
                msg = res.reason
            t.end_failure(msg, status=res.status_code)
            raise APIError(f"{endpoint}: {res.status_code} {msg}")
        t.end_success()
        return res.json()

    def list_orders(self, order_time=None, update_time=None):
        t = logberry.task("Retrieving order list", order_time=order_time, update_time=update_time)

        params = {'list_type': 'customer', 'limit': 5000}
        if order_time is not None:
            params['order_time'] = order_time
        if update_time is not None:
            params['update_time'] = update_time

        orders = []
        while True:
            page = self._get('order/list', offset=len(orders), **params)
            orders.extend(page)
            if len(page) < params['limit']:
                break

        t.end_success(orders=len(orders))
        return orders

    def view_order(self, order_id):
        return self._get('order/view', order_id=order_id)

    def order_items(self, order_id):
        return self._get('order/items', order_id=order_id)

    def id_list(self, type, id_type):
        t = logberry.task("Retrieving ID list", type=type, id_type=id_type)
        boids = self._get('catalog/id_list', type=type, id_type=id_type)['boids']
        t.end_success(items=len(boids))
        return boids

def client(settings: Settings):
    return Client(settings)


_rates = {}

def usd_rate(currency: str, day: date):
    """ECB reference rate to convert currency to USD on the given day.

    Each currency and day is requested at most once; a failure is
    remembered and raised again for later orders needing the same rate.
    """
    k = (currency, day)
    if k not in _rates:
        t = logberry.task("Exchange rate request", currency=currency, date=day.isoformat())
        try:
            res = requests.get(f"{RATES_URL}/{day.isoformat()}",
                               {'base': currency, 'symbols': 'USD'},
                               headers = {'User-Agent': USER_AGENT})
            res.raise_for_status()
            rate = float(res.json()['rates']['USD'])
            if not math.isfinite(rate) or rate <= 0:
                raise ValueError(f"Invalid {currency} rate {rate}")
            _rates[k] = rate
            t.end_success(rate=rate)
        except Exception as e:
            _rates[k] = e
            t.end_failure("Rate not available", error=str(e))
    if isinstance(_rates[k], Exception):
        raise _rates[k]
    return _rates[k]

def amount(v, field='amount'):
    """Monetary value as a float; ValueError if not a finite number."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        f = float(v)
    elif isinstance(v, str) and NUMBER.fullmatch(v.strip()):
        f = float(v)
    else:
        raise ValueError(f"Malformed {field} '{v}'")
    if not math.isfinite(f):
        raise ValueError(f"Malformed {field} '{v}'")
    return f

def _total(view, field):
    if view.get(field) is None or view[field] == '':
        raise ValueError(f"Missing {field}")
    return amount(view[field], field)

def payment_rate(view):
    """Multiplier converting an order's payment currency amounts into USD.

    Exact if paid in USD, else the ECB rate for the order date.
    """
    if not view.get('payment_currency'):
        raise ValueError("Missing payment_currency")
    if view['payment_currency'] == 'USD':
        return 1.0
    return usd_rate(view['payment_currency'], order_day(view))

def _shadow_usd(d, fields, rate):
    """Copy of d with a USD sibling following each present currency field."""
    out = {}
    for k, v in d.items():
        out[k] = v
        if k in fields:
            # Adding 0 normalizes -0.0 from a zero rate.
            out[k + USD_SUFFIX] = v if v is None or v == '' else amount(v, k) * rate + 0.0
    return out

def add_usd(view, items):
    """Order view and items with USD shadows of their currency fields,
    per apps.brickowl.md §1.6.

    Base currency amounts are converted by the effective rate actually
    paid, so that every amount is anchored on the USD value of the
    payment; all are 0 if base_order_total is 0.
    """
    paid = _total(view, 'payment_total')
    total = _total(view, 'base_order_total')
    payment = payment_rate(view)
    base = paid * payment / total if total else 0.0
    usd = _shadow_usd(view, BASE_CURRENCY_FIELDS, base)
    usd = _shadow_usd(usd, PAYMENT_CURRENCY_FIELDS, payment)
    # Exactly what was paid, free of the effective rate's rounding.
    usd['base_order_total_USD'] = usd['payment_total_USD']
    items = [_shadow_usd(i, ITEM_CURRENCY_FIELDS, base) for i in items]
    return usd, items

def canonical_id(oid):
    """Canonical form of an order ID: positive decimal, no leading zeros."""
    s = str(oid).strip()
    if not re.fullmatch(r'[0-9]+', s) or int(s) == 0:
        raise ValueError(f"Invalid order ID '{oid}'")
    return str(int(s))

def parse_timestamp(v, field):
    """Unix timestamp as an int, None if empty; ValueError if malformed."""
    if v is None or v == '':
        return None
    if isinstance(v, bool) or not (isinstance(v, int) or (isinstance(v, str) and re.fullmatch(r'[0-9]+', v))):
        raise ValueError(f"Malformed {field} '{v}'")
    try:
        datetime.fromtimestamp(int(v), timezone.utc)
    except (OverflowError, OSError, ValueError):
        raise ValueError(f"Malformed {field} '{v}'")
    return int(v)

def utc_iso(ts):
    """ISO 8601 UTC text of a Unix timestamp, as stockist stores times."""
    return datetime.fromtimestamp(ts, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def parse_utc_iso(s):
    """Unix timestamp of ISO 8601 UTC text with a Z suffix; ValueError if
    malformed."""
    if not isinstance(s, str) or not s.endswith('Z'):
        raise ValueError(f"Malformed UTC time '{s}'")
    try:
        return datetime.fromisoformat(s[:-1] + '+00:00').timestamp()
    except (OverflowError, OSError, ValueError):
        raise ValueError(f"Malformed UTC time '{s}'")

def _iso_order_time(view):
    """Order's iso_order_time as an aware datetime in Brick Owl's own
    timezone, None if missing; ValueError if malformed."""
    v = view.get('iso_order_time')
    if v is None or v == '':
        return None
    try:
        dt = datetime.fromisoformat(v)
    except (TypeError, ValueError):
        raise ValueError(f"Malformed iso_order_time '{v}'")
    if dt.utcoffset() is None:
        raise ValueError(f"Malformed iso_order_time '{v}', no UTC offset")
    return dt

def order_time(view):
    """Unix timestamp the order was placed, per its iso_order_time; None
    if missing, ValueError if malformed."""
    dt = _iso_order_time(view)
    if dt is None:
        return None
    try:
        ts = dt.timestamp()
    except (OverflowError, OSError, ValueError):
        raise ValueError(f"Malformed iso_order_time '{view['iso_order_time']}'")
    return int(ts) if ts.is_integer() else ts

def order_day(view):
    """Calendar date the order was placed, in Brick Owl's own timezone
    rather than UTC, per apps.brickowl.md §1.6."""
    dt = _iso_order_time(view)
    if dt is None:
        raise ValueError("Missing iso_order_time")
    return dt.date()

def status_key(s):
    """Status name normalized for matching: any case, no spaces, hyphens, or underscores."""
    return ''.join(c for c in s.lower() if c not in ' -_')

_STATUS_KEYS: Final[tuple] = tuple(status_key(n) for n in STATUSES)

def status_id(value):
    """Numeric status ID for a state name or ID, None if empty.

    Raises ValueError if the status is not recognized."""
    if value is None or value == '':
        return None
    s = str(value).strip()
    if re.fullmatch(r'[0-9]+', s):
        if int(s) < len(STATUSES):
            return int(s)
    elif status_key(s) in _STATUS_KEYS:
        return _STATUS_KEYS.index(status_key(s))
    raise ValueError(f"Unrecognized order status '{value}'")

def view_status(view):
    """Numeric status ID of an order, from its ID if given else its name;
    None if missing.  Raises ValueError if unrecognized."""
    for k in ('status_id', 'status'):
        v = view.get(k)
        if v is not None and v != '':
            try:
                return status_id(v)
            except ValueError:
                raise ValueError(f"Unrecognized {k} '{v}'")
    return None

def order_status(view):
    """Numeric status ID of an order as a string, None if missing or unrecognized."""
    try:
        sid = view_status(view)
    except ValueError:
        return None
    return None if sid is None else str(sid)

def display_name(name):
    """Store or item name with HTML entities unescaped and control
    characters stripped, per apps.brickowl.md §1.4."""
    return ''.join(c for c in html.unescape(name)
                   if unicodedata.category(c) not in ('Cc', 'Cf'))

def display_item_name(name):
    """Item name as display_name, whitespace trimmed and any "LEGO "
    prefix stripped, per apps.brickowl.md §1.4."""
    return display_name(name).strip().removeprefix('LEGO ').strip()


# Item conditions, greatest first, per apps.brickowl.md §1.9.
CONDITIONS: Final[tuple] = (('new', 'New'), ('newc', 'New (Complete)'), ('news', 'New (Sealed)'),
                            ('newi', 'New (Incomplete)'), ('usedn', 'Used (Like New)'),
                            ('usedg', 'Used (Good)'), ('usedc', 'Used (Complete)'),
                            ('usedi', 'Used (Incomplete)'), ('useda', 'Used (Acceptable)'))


def _unique(values):
    return list(dict.fromkeys(v for v in values if v))


CATALOG_TYPES: Final[tuple] = ('Part', 'Set', 'Minifigure', 'Gear', 'Sticker',
                               'Minibuild', 'Instructions', 'Packaging')
NATURAL_ID_SEPARATOR: Final[str] = '/'
# Color suffix of a BOID.
BOID_COLOR: Final = re.compile(r'-[0-9]+$')

def _ids_of(item, *id_types):
    """Deduplicated IDs of an item of the given types, grouped by type in
    that order and otherwise as given."""
    ids = item.get('ids') or []
    return _unique(str(x.get('id') or '').strip()
                   for t in id_types for x in ids if x.get('type') == t)

class NaturalIDs:
    """Natural IDs of order items, per apps.brickowl.md §1.8.

    BrickLink IDs are not given in order items, so they are looked up
    from the catalog as needed, at most once per item type.  A failed
    lookup is passed to the caller's warn callback and the item falls
    back to its BOID.
    """

    def __init__(self, api):
        self.api = api
        self._bl_ids = {}

    def _bl_ids_of(self, item):
        boid, type = item.get('boid'), item.get('type')
        if not boid or type not in CATALOG_TYPES:
            return []
        if type not in self._bl_ids:
            try:
                self._bl_ids[type] = self.api.id_list(type, 'bl_item_no')
            except Exception as e:
                # Not retried, to spare the API quota.
                self._bl_ids[type] = e
        bl_ids = self._bl_ids[type]
        if isinstance(bl_ids, Exception):
            raise bl_ids
        ids = bl_ids.get(boid) or bl_ids.get(BOID_COLOR.sub('', boid)) or []
        return _unique([ids] if isinstance(ids, str) else ids)

    def __call__(self, item, warn=None):
        ids = (_ids_of(item, 'set_number') or
               _ids_of(item, 'design_id', 'obsolete_design_id') or
               _ids_of(item, 'item_no'))
        if not ids:
            try:
                ids = self._bl_ids_of(item)
            except Exception as e:
                if warn:
                    warn(item, e)
        ids = ids or _unique([item.get('boid')])
        return NATURAL_ID_SEPARATOR.join(ids)

def add_natural_ids(items, natural_ids, warn=None):
    """Order items with a natural_id field following each one's boid.

    warn(item, error) is called for each item whose BrickLink ID lookup
    failed."""
    out = []
    for i in items:
        nid = natural_ids(i, warn)
        item = {}
        for k, v in i.items():
            if k != 'natural_id':
                item[k] = v
            if k == 'boid':
                item['natural_id'] = nid
        item.setdefault('natural_id', nid)
        out.append(item)
    return out
