if __name__ != '__main__':
    raise Error("This is a script, not intended to be imported")

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional
import argparse
import os
import sys

from wcwidth import wcswidth

from apps.brickowl import common
from stockist import brickowl


PROG = 'list-orders'

CENT = Decimal('0.01')
TIME_FORMAT = '%Y-%m-%d %H:%M'

# Sort tags and whether each defaults to descending.
SORT_TAGS = {'id': True, 'time': True, 'date': True, 'store': False, 'status': False, 'total': True}
SORT_DIRECTIONS = {'asc': False, 'desc': True}

# Column labels and whether each is right justified.
COLUMNS = (('Order ID', False), ('Order Time', False), ('Store ID', False),
           ('Store Name', False), ('Total', True), ('Status', False))
TOTAL_COLUMN = 4


#-- Arguments -------------------------------------------------------------

def parse_sort(s):
    """Sort criteria as a list of (tag, descending) pairs."""
    criteria = []
    for e in s.split(','):
        tag, sep, direction = e.partition(':')
        tag = tag.strip().lower()
        if tag not in SORT_TAGS:
            raise argparse.ArgumentTypeError(
                f"Invalid sort criteria '{s}', tags must be from: {', '.join(SORT_TAGS)}")
        if tag in (t for t, _ in criteria):
            raise argparse.ArgumentTypeError(f"Invalid sort criteria '{s}', repeated tag '{tag}'")
        if sep:
            direction = direction.strip().lower()
            if direction not in SORT_DIRECTIONS:
                raise argparse.ArgumentTypeError(
                    f"Invalid sort criteria '{s}', direction must be asc or desc")
            criteria.append((tag, SORT_DIRECTIONS[direction]))
        else:
            criteria.append((tag, SORT_TAGS[tag]))
    return criteria

class Once(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(namespace, self.dest) is not None:
            parser.error(f"{option_string} may only be given once")
        setattr(namespace, self.dest, values)

parser = argparse.ArgumentParser(prog='python -m apps.brickowl.list-orders',
                                 description='List basic information about cached Brick Owl orders')
common.add_config_arguments(parser)
common.add_scope_arguments(parser)
parser.add_argument('--csv', action='store_true', help='Output as CSV')
parser.add_argument('--sort', type=parse_sort, action=Once,
                    help=f'Comma separated sort tags from {", ".join(SORT_TAGS)}, '
                         'each optionally suffixed :asc or :desc (default time,id)')
args = parser.parse_args()


def fail(msg):
    print(f"{PROG}: error: {msg}", file=sys.stderr)
    sys.exit(1)

try:
    settings = common.load_settings(args)
except Exception as e:
    fail(f"Could not load configuration: {e}")


#-- Orders ----------------------------------------------------------------

@dataclass
class Row:
    id: int
    time: Optional[float]
    store_id: Optional[str]
    store_name: Optional[str]
    total: Optional[Decimal]
    status: Optional[int]

def _text(view, field):
    v = view.get(field)
    if common.empty(v):
        return None
    if isinstance(v, bool) or not isinstance(v, (str, int)):
        raise common.OrderError(f"invalid {field} '{v}'")
    return str(v)

def _total(view):
    """Payment total less refunds, in USD rounded to cents."""
    payment = common.money(view, 'payment_total_USD')
    refund = common.money(view, 'refund_total_USD')
    if payment is None:
        if refund:
            raise common.OrderError("refund_total_USD given without payment_total_USD")
        return None
    try:
        total = (payment - (refund or 0)).quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        raise common.OrderError("total out of range")
    return abs(total) if total == 0 else total

def _store_name(view):
    """Store display name, whitespace trimmed; None if blank."""
    name = _text(view, 'store_name')
    return (brickowl.display_name(name).strip() or None) if name is not None else None

def order_row(view):
    """Listing row of an order, validating each reported field."""
    return Row(id=int(view['order_id']),
               time=common.order_time(view),
               store_id=_text(view, 'store_id'),
               store_name=_store_name(view),
               total=_total(view),
               status=common.order_status(view))


try:
    orders = common.scoped_orders(args, settings.cache)
except common.ScopeError as e:
    fail(str(e))

rows = []
for oid, fn, data in orders:
    try:
        rows.append(order_row(data['view']))
    except common.OrderError as e:
        fail(f"Order {oid} ({fn}) {e}")


#-- Sort ------------------------------------------------------------------

def _status_main(r):
    return r.status if r.status is not None and r.status <= int(brickowl.STATUS_RECEIVED) else None

def _status_tail(r):
    """On Hold, then Cancelled, then missing, regardless of direction."""
    return {int(brickowl.STATUS_ON_HOLD): 0, int(brickowl.STATUS_CANCELLED): 1}.get(r.status, 2)

SORT_KEYS = {
    'id': lambda r: r.id,
    'time': lambda r: r.time,
    'date': lambda r: None if r.time is None else brickowl.local_time(r.time).date(),
    'store': lambda r: None if r.store_name is None else common.natural_key(r.store_name),
    'status': _status_main,
    'total': lambda r: r.total,
}

def sort_pass(rows, key, desc, tail=lambda r: 0):
    """Stable sort on key; rows without a key value follow in tail order
    regardless of direction."""
    main = [r for r in rows if key(r) is not None]
    rest = [r for r in rows if key(r) is None]
    main.sort(key=key, reverse=desc)
    rest.sort(key=tail)
    return main + rest

def complete_sort(criteria):
    """Criteria with time and ID tiebreakers appended, following the
    direction of the last date or time criterion."""
    tags = [t for t, _ in criteria]
    timed = [desc for t, desc in criteria if t in ('date', 'time')]
    def appended(tag):
        return (tag, timed[-1] if timed else SORT_TAGS[tag])

    if 'id' in tags:
        return criteria
    if 'time' in tags:
        return criteria + [appended('id')]
    return criteria + [appended('time'), appended('id')]

for tag, desc in reversed(complete_sort(args.sort or [])):
    if tag == 'store':
        rows = sort_pass(rows, lambda r: None if r.store_id is None else common.natural_key(r.store_id), False)
    rows = sort_pass(rows, SORT_KEYS[tag], desc, _status_tail if tag == 'status' else lambda r: 0)


#-- Output ----------------------------------------------------------------

def cells(r):
    return [str(r.id),
            brickowl.local_time(r.time).strftime(TIME_FORMAT) if r.time is not None else '',
            r.store_id or '',
            r.store_name or '',
            r.total,
            brickowl.STATUSES[r.status] if r.status is not None else '']

def width(s):
    w = wcswidth(s)
    return w if w >= 0 else len(s)

def dollars(total):
    if total is None:
        return ''
    return f"-${-total}" if total < 0 else f"${total}"

def text_lines(table):
    table = [table[0]] + [row[:TOTAL_COLUMN] + [dollars(row[TOTAL_COLUMN])] + row[TOTAL_COLUMN + 1:]
                          for row in table[1:]]
    widths = [max(width(row[c]) for row in table) for c in range(len(COLUMNS))]
    for row in table:
        padded = []
        for c, (s, (_, right)) in enumerate(zip(row, COLUMNS)):
            fill = ' ' * (widths[c] - width(s))
            padded.append(fill + s if right else s + fill)
        yield ' '.join(padded).rstrip()

def csv_lines(table):
    def quote(s):
        return '"' + s.replace('"', '""') + '"'
    yield ','.join(quote(s) for s in table[0])
    for row in table[1:]:
        yield ','.join(('' if s is None else str(s)) if c == TOTAL_COLUMN else quote(s)
                       for c, s in enumerate(row))

table = [[label for label, _ in COLUMNS]] + [cells(r) for r in rows]

try:
    for line in (csv_lines if args.csv else text_lines)(table):
        sys.stdout.write(line + '\n')
    sys.stdout.flush()
except BrokenPipeError:
    os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    sys.exit(1)
