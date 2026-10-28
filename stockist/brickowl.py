
import logberry
import tjawn

from typing import Optional, Final
from dataclasses import dataclass, field
from dacite import from_dict

from datetime import datetime, date
import html
import re
import requests


BRICKOWL: Final[str] = 'brickowl'

API_URL: Final[str] = 'https://api.brickowl.com/v1'
RATES_URL: Final[str] = 'https://api.frankfurter.dev/v1'
USER_AGENT: Final[str] = 'stockist-brickowl/1.0'

STATUS_CANCELLED: Final[str] = '8'

UNKNOWN_ITEM: Final[str] = '(unknown item)'


@dataclass
class Settings:
    api_key: str

def load_configuration(fn='.conf/brickowl.jawn'):
    return from_dict(data_class=Settings, data=tjawn.loads(open(fn, "rt").read()))


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
        res.raise_for_status()
        t.end_success()
        return res.json()

    def list_orders(self, order_time=None):
        t = logberry.task("Retrieving order list", order_time=order_time)

        params = {'list_type': 'customer', 'limit': 5000}
        if order_time is not None:
            params['order_time'] = order_time

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
    """ECB reference rate to convert currency to USD on the given day."""
    k = (currency, day)
    if k not in _rates:
        t = logberry.task("Exchange rate request", currency=currency, date=day.isoformat())
        res = requests.get(f"{RATES_URL}/{day.isoformat()}",
                           {'base': currency, 'symbols': 'USD'},
                           headers = {'User-Agent': USER_AGENT})
        res.raise_for_status()
        _rates[k] = float(res.json()['rates']['USD'])
        t.end_success(rate=_rates[k])
    return _rates[k]

def order_rate(view):
    """Multiplier converting an order's base currency amounts into USD.

    Exact if the order was in or paid in USD, else the ECB rate for the
    order date.
    """
    if view['base_currency'] == 'USD':
        return 1.0
    if view['payment_currency'] == 'USD':
        return float(view['payment_total']) / float(view['base_order_total'])
    return usd_rate(view['base_currency'], order_placed(view).date())

def order_placed(view):
    return datetime.fromtimestamp(int(view['order_time']))

def is_cancelled(view):
    return view.get('status_id') == STATUS_CANCELLED or view.get('status') == 'Cancelled'


def _unique(values):
    return list(dict.fromkeys(v for v in values if v))

def _item_ids(item, id_type):
    return _unique(x['id'] for x in item['ids'] if x['type'] == id_type)

def needs_design_ids(item):
    return item['type'] == 'Part' and not _item_ids(item, 'design_id')

def natural_id(item, design_ids={}, bl_ids={}):
    """LEGO design ID for parts, set number for others, BrickLink ID for
    minifigures; falling back on the ID list and then the item name."""
    boid = item['boid']

    if item['type'] == 'Minifigure':
        ids = _unique(bl_ids.get(boid, []))
    else:
        ids = _item_ids(item, 'design_id') or _item_ids(item, 'set_number')
        if not ids and item['type'] == 'Part':
            ids = _unique(design_ids.get(boid, []) or
                          design_ids.get(boid.split('-')[0], []))
            if not ids:
                m = re.search(r'\((\d+[a-z]?(?: / \d+[a-z]?)*)\)$', html.unescape(item['name']))
                if m:
                    ids = m.group(1).split(' / ')

    return ' / '.join(ids)


@dataclass
class Item:
    order_item_id: str
    boid: str
    name: str
    type: str
    color: str
    condition: str
    natural_id: str
    quantity: int
    price: float
    subtotal: float
    adjusted_price: float = 0.0
    adjusted_subtotal: float = 0.0

    @property
    def key(self):
        """Summary grouping key; deleted catalog items are each distinct."""
        return self.boid if self.boid else f"#{self.order_item_id}"

@dataclass
class Order:
    order_id: str
    store_name: str
    placed: datetime
    rate: float
    subtotal: float
    shipping: float
    taxes: float
    discounts: float
    total: float
    items: list[Item] = field(default_factory=list)

    @property
    def lots(self):
        return len(set(i.key for i in self.items))

    @property
    def quantity(self):
        return sum(i.quantity for i in self.items)


def _f(v):
    return float(v) if v else 0.0

def as_order(view, items, rate, design_ids={}, bl_ids={}):
    """Build an Order in USD, net of refunds, with item adjusted prices."""

    t = logberry.task("Process order", order_id=view['order_id'],
                      currency=view['base_currency'], rate=rate)

    order = Order(order_id=view['order_id'],
                  store_name=html.unescape(view['store_name']),
                  placed=order_placed(view),
                  rate=rate,
                  subtotal=0.0,
                  shipping=(_f(view['ship_total']) - _f(view['refund_shipping'])) * rate,
                  taxes=(_f(view['tax_amount']) + _f(view['eu_duty']) - _f(view['refund_eu_duty'])) * rate,
                  discounts=(_f(view['coupon_discount']) + _f(view['refund_adjustment'])) * rate,
                  total=(_f(view['base_order_total']) - _f(view['refund_total'])) * rate)

    base_subtotal = 0.0
    for i in items:
        qty = int(i['ordered_quantity']) - int(i['refunded_quantity'] or 0)
        if qty <= 0:
            continue

        base_subtotal += _f(i['base_price']) * qty
        price = _f(i['base_price']) * rate
        order.items.append(Item(order_item_id=i['order_item_id'],
                                boid=i['boid'],
                                name=html.unescape(i['name']) or UNKNOWN_ITEM,
                                type=i['type'],
                                color=i['color_name'],
                                condition=i['condition'],
                                natural_id=natural_id(i, design_ids, bl_ids),
                                quantity=qty,
                                price=price,
                                subtotal=price * qty))

    order.subtotal = sum(i.subtotal for i in order.items)

    expected = _f(view['sub_total']) - _f(view['refund_subtotal'])
    if abs(base_subtotal - expected) > 0.01:
        t.warning("Item subtotal does not match order",
                  items=round(base_subtotal, 2), order=round(expected, 2))

    computed = order.subtotal + order.shipping + _f(view['eu_duty']) * rate - order.discounts
    if abs(computed - order.total) > 0.01:
        t.warning("Order total does not reconcile",
                  computed=round(computed, 2), total=round(order.total, 2))

    for i in order.items:
        i.adjusted_subtotal = i.subtotal * order.total / order.subtotal if order.subtotal else 0.0
        i.adjusted_price = i.adjusted_subtotal / i.quantity

    order.items.sort(key=lambda i: i.subtotal, reverse=True)

    t.end_success(items=len(order.items), total=round(order.total, 2))
    return order


def weighted_stats(pairs):
    """Min, max, median, mean, and sum of (unit price, quantity) pairs,
    weighted by quantity."""
    pairs = sorted(pairs)
    n = sum(q for _, q in pairs)
    total = sum(p * q for p, q in pairs)

    def unit(k):
        for p, q in pairs:
            if k < q:
                return p
            k -= q

    median = (unit((n - 1) // 2) + unit(n // 2)) / 2

    return pairs[0][0], pairs[-1][0], median, total / n, total
