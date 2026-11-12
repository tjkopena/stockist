if __name__ != '__main__':
    raise Error("This is a script, not intended to be imported")

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from os import path
from typing import Optional
import argparse
import os
import re
import sys
import tempfile

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font

from apps.brickowl import common
from stockist import brickowl


PROG = 'summarize-orders'

TEMP_PREFIX = '.summarize-orders-'
TEMP_SUFFIX = '.tmp'

CURRENCY = '"$"#,##0.00'
DATETIME = 'yyyy-mm-dd hh:mm'

SUMMARY_TITLE = 'Summary'

# Column label, width, and number format.
SUMMARY_COLUMNS = (
    ('BOID', 14, None),
    ('Natural ID', 14, None),
    ('Type', 12, None),
    ('Name', 60, None),
    ('Color', 20, None),
    ('Quantity', 10, None),
    ('Minimum Adjusted Price', 14, CURRENCY),
    ('Maximum Adjusted Price', 14, CURRENCY),
    ('Median Adjusted Price', 14, CURRENCY),
    ('Mean Adjusted Price', 14, CURRENCY),
    ('Adjusted Subtotal', 14, CURRENCY),
    ('Minimum Price', 14, CURRENCY),
    ('Maximum Price', 14, CURRENCY),
    ('Median Price', 14, CURRENCY),
    ('Mean Price', 14, CURRENCY),
    ('Subtotal', 14, CURRENCY),
    ('Orders', 30, None),
)

DETAILS_COLUMNS = (
    ('BOID', 14, None),
    ('Natural ID', 14, None),
    ('Type', 12, None),
    ('Name', 60, None),
    ('Color', 20, None),
    ('Condition', 18, None),
    ('Quantity', 10, None),
    ('Adjusted Price', 14, CURRENCY),
    ('Adjusted Subtotal', 14, CURRENCY),
    ('Price', 14, CURRENCY),
    ('Subtotal', 14, CURRENCY),
)

# Sheet labels: Excel's limit and forbidden characters.
SHEET_NAME_MAX = 31
SHEET_NAME_FORBIDDEN = re.compile(r"[\[\]:*?/\\]")
SHEET_DATE = '%Y%m%d'
# Store portion of a label, leaving room for the date and a " (99)" suffix.
SHEET_STORE_MAX = SHEET_NAME_MAX - len(' YYYYMMDD') - len(' (99)')

CONDITION_RANK = {code: rank for rank, (code, _) in enumerate(brickowl.CONDITIONS)}
CONDITION_LABEL = dict(brickowl.CONDITIONS)


parser = argparse.ArgumentParser(prog='python -m apps.brickowl.summarize-orders',
                                 description='Summarize cached Brick Owl orders into an XLSX workbook')
common.add_config_arguments(parser)
common.add_scope_arguments(parser)
parser.add_argument('--out', help='Output XLSX filename (default from configuration file, else '
                                  'data/brickowl/orders.xlsx)')
args = parser.parse_args()


def fail(msg):
    print(f"{PROG}: error: {msg}", file=sys.stderr)
    sys.exit(1)

try:
    settings = common.load_settings(args, options=('out',))
except Exception as e:
    fail(f"Could not load configuration: {e}")

out = args.out or path.join('data', 'brickowl', 'orders.xlsx')
if path.isdir(out):
    fail(f"Output '{out}' is a folder")


#-- Orders ----------------------------------------------------------------

@dataclass
class Line:
    position: int
    boid: str
    natural_id: str
    type: str
    name: str
    color: str
    condition: str
    condition_rank: Optional[int]
    quantity: int
    price: Decimal
    adjusted_subtotal: Optional[Decimal] = None
    adjusted_price: Optional[Decimal] = None

    @property
    def subtotal(self):
        return self.price * self.quantity

@dataclass
class Order:
    id: str
    time: float
    store_id: str
    store_name: str
    status: str
    total: Decimal
    lines: list[Line] = field(default_factory=list)

    @property
    def included(self):
        """Whether the order contributes to the summary sheet."""
        return self.total >= 0

def _text(d, field):
    v = d.get(field)
    return '' if common.empty(v) else str(v).strip()

def _quantity(item, field):
    v = item.get(field)
    if isinstance(v, str) and re.fullmatch(r'\s*[0-9]+\s*', v):
        return int(v)
    if isinstance(v, int) and not isinstance(v, bool) and v >= 0:
        return v
    raise common.OrderError(f"malformed {field} '{v}'")

def _line(position, item):
    if not isinstance(item, dict):
        raise common.OrderError(f"corrupted, item {position + 1} is not a map")

    ordered = _quantity(item, 'ordered_quantity')
    refunded = _quantity(item, 'refunded_quantity')
    if refunded > ordered:
        raise common.OrderError(f"item {position + 1} refunded_quantity exceeds ordered_quantity")

    price = common.money(item, 'base_price_USD')
    if price is None:
        raise common.OrderError(f"item {position + 1} missing base_price_USD")
    if price < 0:
        raise common.OrderError(f"item {position + 1} negative base_price_USD")

    code = _text(item, 'full_con').lower()
    return Line(position=position,
                boid=_text(item, 'boid'),
                natural_id=_text(item, 'natural_id'),
                type=_text(item, 'type'),
                name=brickowl.display_name(_text(item, 'name')).strip(),
                color=_text(item, 'color_name'),
                condition=CONDITION_LABEL.get(code) or _text(item, 'condition'),
                condition_rank=CONDITION_RANK.get(code),
                quantity=ordered - refunded,
                price=price + 0)

def _total(view):
    """Payment total less refunds, in USD, per apps.brickowl.md §1.7."""
    payment = common.money(view, 'payment_total_USD')
    if payment is None:
        raise common.OrderError("missing payment_total_USD")
    return payment - (common.money(view, 'refund_total_USD') or 0)

def _status(view):
    """Status label, the given text if unrecognized."""
    try:
        sid = brickowl.view_status(view)
    except ValueError:
        return _text(view, 'status')
    return '' if sid is None else brickowl.STATUSES[sid]

def adjust(order):
    """Adjusted prices and subtotals of an order's lines, per §1.1."""
    subtotal = sum(l.subtotal for l in order.lines)
    net = sum(l.quantity for l in order.lines)
    for l in order.lines:
        if l.quantity == 0 or order.total < 0:
            continue
        if subtotal > 0:
            l.adjusted_subtotal = order.total * l.subtotal / subtotal
            l.adjusted_price = l.adjusted_subtotal / l.quantity
        else:
            l.adjusted_price = order.total / net
            l.adjusted_subtotal = l.adjusted_price * l.quantity

def read_order(view, items):
    time = common.order_time(view)
    if time is None:
        raise common.OrderError("missing iso_order_time")
    if not isinstance(items, list):
        raise common.OrderError("corrupted, missing items")

    order = Order(id=brickowl.canonical_id(view['order_id']),
                  time=time,
                  store_id=_text(view, 'store_id'),
                  store_name=brickowl.display_name(_text(view, 'store_name')).strip(),
                  status=_status(view),
                  total=_total(view),
                  lines=[_line(p, i) for p, i in enumerate(items)])
    adjust(order)
    return order


try:
    scoped = common.scoped_orders(args, settings.cache)
except common.ScopeError as e:
    fail(str(e))

if not scoped:
    fail("No orders in scope")

orders = []
for oid, fn, data in scoped:
    try:
        orders.append(read_order(data['view'], data.get('items')))
    except common.OrderError as e:
        fail(f"Order {oid} ({fn}) {e}")


#-- Sort ------------------------------------------------------------------

def _missing_last(s):
    """Natural sort key with blank strings last."""
    return (not s, common.natural_key(s))

def _descending_missing_last(v):
    return (v is None, -v if v is not None else 0)

# Most recent first, then order ID.
orders.sort(key=lambda o: (o.time, int(o.id)), reverse=True)

for o in orders:
    o.lines.sort(key=lambda l: (_descending_missing_last(l.adjusted_subtotal),
                                -l.quantity,
                                _missing_last(l.boid),
                                (l.condition_rank is None, l.condition_rank or 0),
                                l.position))


#-- Summary ---------------------------------------------------------------

def weighted_stats(values):
    """Minimum, maximum, median, and mean of (value, quantity) pairs,
    each value repeated by its quantity."""
    values = sorted(values, key=lambda v: v[0])
    n = sum(q for _, q in values)

    def nth(i):
        for v, q in values:
            if i < q:
                return v
            i -= q

    return (values[0][0], values[-1][0],
            (nth((n - 1) // 2) + nth(n // 2)) / 2,
            sum(v * q for v, q in values) / n)

@dataclass
class Item:
    """Aggregate of an item's contributing lines, in workbook order."""
    lines: list[Line] = field(default_factory=list)
    orders: dict[str, int] = field(default_factory=lambda: defaultdict(int))

items = {}
for o in orders:
    if not o.included:
        continue
    for l in o.lines:
        if l.quantity == 0:
            continue
        # Blank BOIDs are each distinct.
        item = items.setdefault(l.boid or (o.id, l.position), Item())
        item.lines.append(l)
        item.orders[o.id] += l.quantity

def summary_row(item):
    # Descriptive fields are taken from the most recent order.
    first = item.lines[0]
    quantity = sum(l.quantity for l in item.lines)
    adjusted = weighted_stats([(l.adjusted_price, l.quantity) for l in item.lines])
    plain = weighted_stats([(l.price, l.quantity) for l in item.lines])
    contributors = sorted(item.orders.items(), key=lambda o: (-o[1], int(o[0])))
    return [first.boid, first.natural_id, first.type, first.name, first.color, quantity,
            *adjusted, sum(l.adjusted_subtotal for l in item.lines),
            *plain, sum(l.subtotal for l in item.lines),
            ', '.join(oid for oid, _ in contributors)]

# Python's sort is stable, so ties beyond BOID remain in workbook order.
summary = sorted((summary_row(i) for i in items.values()),
                 key=lambda r: (-r[10], -r[5], _missing_last(r[3]), _missing_last(r[0])))


#-- Sheet labels ----------------------------------------------------------

def sanitize(name):
    name = SHEET_NAME_FORBIDDEN.sub('', name)
    return re.sub(r'\s+', ' ', name).strip(" '")

def short(text, n):
    return text[:n].rstrip(" '")

def store_label(o):
    """Shortened and sanitized store name; blank if the name is."""
    return short(sanitize(o.store_name), SHEET_STORE_MAX)

# Stores whose short names collide case-insensitively include their IDs.
store_ids = defaultdict(set)
for o in orders:
    store_ids[store_label(o).casefold()].add(o.store_id)

def store_part(o):
    label = store_label(o)
    if len(store_ids[label.casefold()]) == 1:
        return label or 'Unknown'
    tag = f"#{o.store_id}" if o.store_id else '#'
    return (short(label, SHEET_STORE_MAX - len(tag) - 1) + ' ' + tag).strip()

same_day = defaultdict(list)
for o in orders:
    same_day[(o.store_id, brickowl.local_time(o.time).date())].append(o)

sheet_labels = {}
used = {SUMMARY_TITLE.casefold(), 'history'}
for o in orders:
    group = same_day[(o.store_id, brickowl.local_time(o.time).date())]
    suffix = f" ({len(group) - group.index(o)})" if len(group) > 1 else ''
    stamp = f" {brickowl.local_time(o.time):{SHEET_DATE}}{suffix}"
    label = short(store_part(o), SHEET_NAME_MAX - len(stamp)) + stamp
    if label.casefold() in used:
        # Last resort should the rules above still collide, e.g., a store
        # name itself ending in a parenthesized number.
        label = short(store_part(o), SHEET_NAME_MAX - len(stamp) - len(f" ~{o.id}")) + f" ~{o.id}" + stamp
    used.add(label.casefold())
    sheet_labels[o.id] = label


#-- Workbook --------------------------------------------------------------

bold = Font(bold=True)

def put(ws, row, column, value, fmt=None):
    if isinstance(value, Decimal):
        value = float(value)
    elif isinstance(value, str):
        value = ILLEGAL_CHARACTERS_RE.sub('', value)
    cell = ws.cell(row=row, column=column, value=value)
    if isinstance(value, str) and value.startswith('='):
        # Text, never a formula.
        cell.data_type = 's'
    if fmt:
        cell.number_format = fmt
    return cell

def header(ws, row, columns):
    for c, (label, width, _) in enumerate(columns, start=1):
        put(ws, row, c, label).font = bold
        ws.column_dimensions[ws.cell(row=row, column=c).column_letter].width = width

def rows(ws, start, data, columns):
    for r, values in enumerate(data, start=start):
        for c, (value, (_, _, fmt)) in enumerate(zip(values, columns), start=1):
            put(ws, r, c, value, fmt)

def _id(s):
    return int(s) if s.isdigit() else s

wb = Workbook()

ws = wb.active
ws.title = SUMMARY_TITLE
header(ws, 1, SUMMARY_COLUMNS)
rows(ws, 2, summary, SUMMARY_COLUMNS)
ws.freeze_panes = 'A2'

for o in orders:
    ws = wb.create_sheet(sheet_labels[o.id])
    boids = {l.boid or l.position for l in o.lines if l.quantity > 0}
    overview = (('Store Name', o.store_name, None),
                ('Store ID', _id(o.store_id), None),
                ('Order ID', int(o.id), None),
                ('Order Date', brickowl.local_time(o.time).replace(tzinfo=None), DATETIME),
                ('Order Status', o.status, None),
                ('BOIDs', len(boids), None),
                ('Quantity', sum(l.quantity for l in o.lines), None),
                ('Total', o.total, CURRENCY))
    for c, (label, value, fmt) in enumerate(overview):
        put(ws, 1, 2 * c + 1, label).font = bold
        put(ws, 1, 2 * c + 2, value, fmt)

    header(ws, 2, DETAILS_COLUMNS)
    rows(ws, 3, [[l.boid, l.natural_id, l.type, l.name, l.color, l.condition, l.quantity,
                  l.adjusted_price, l.adjusted_subtotal, l.price, l.subtotal]
                 for l in o.lines],
         DETAILS_COLUMNS)
    ws.freeze_panes = 'A3'


#-- Output ----------------------------------------------------------------

def missing_folders(folder):
    """Folders that must be created for folder to exist, deepest first."""
    missing = []
    while folder and not path.exists(folder):
        missing.append(folder)
        folder = path.dirname(folder)
    return missing

folder = path.dirname(path.abspath(out))
created = missing_folders(folder)
temp = None
try:
    os.makedirs(folder, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=TEMP_PREFIX, suffix=TEMP_SUFFIX, dir=folder)
    os.close(fd)
    wb.save(temp)
    os.replace(temp, out)
except Exception as e:
    if temp is not None:
        try:
            os.remove(temp)
        except OSError:
            pass
    for f in created:
        try:
            os.rmdir(f)
        except OSError:
            break
    fail(f"Could not write '{out}': {getattr(e, 'strerror', None) or e}")

print(f"Wrote {len(orders)} orders, {len(summary)} items to {out}")
