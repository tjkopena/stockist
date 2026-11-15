from datetime import timedelta
from decimal import Decimal, InvalidOperation
from os import path
import argparse
import os
import re

from stockist import brickowl

import tjawn


RANGE_SEP = '::'
CACHE_FILE = re.compile(r'order-([1-9][0-9]*)\.jawn')

DEFAULT_IMAGES = path.join('data', 'brickowl', 'images')
# BOIDs are used as image cache filenames, so must be plain names.
BOID_FILENAME = re.compile(r'[0-9A-Za-z][0-9A-Za-z_-]*')


#-- Configuration ---------------------------------------------------------

def add_config_arguments(parser):
    parser.add_argument('--conf', help=f'Configuration file (default {brickowl.DEFAULT_CONF})')
    parser.add_argument('--key', help='Brick Owl API key (default from configuration file)')
    parser.add_argument('--cache',
                        help=f'Order cache folder (default from configuration file, else {brickowl.DEFAULT_CACHE})')

def add_images_argument(parser):
    parser.add_argument('--images',
                        help=f'Image cache folder (default from configuration file, else {DEFAULT_IMAGES})')

def image_path(images, boid, size):
    """Cached image file for a BOID at the given size in pixels."""
    return path.join(images, f"{boid}.{size}px.png")

def load_settings(args, options=()):
    """Settings from the configuration file, overridden by the command line.

    An explicitly given configuration file must exist; the default one
    is optional.  Scope directives in the configuration file are applied
    to args only if none were given on the command line, as are the
    app-specific options named, each individually."""
    if args.conf:
        data = brickowl.read_configuration(args.conf)
    elif path.exists(brickowl.DEFAULT_CONF):
        data = brickowl.read_configuration(brickowl.DEFAULT_CONF)
    else:
        data = {}

    settings = brickowl.settings_from(data)
    apply_config_scope(args, data)
    for key in options:
        if getattr(args, key, None) is None and data.get(key) is not None:
            setattr(args, key, str(data[key]))

    if args.key:
        settings.api_key = args.key
    if args.cache:
        settings.cache = args.cache

    return settings


#-- Order Scope -----------------------------------------------------------

def parse_ids(s):
    try:
        ids = [brickowl.canonical_id(o) for o in s.split(',')]
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid order ID list '{s}'")
    if len(set(ids)) != len(ids):
        raise argparse.ArgumentTypeError(f"Invalid order ID list '{s}', repeated order ID")
    return ids

def parse_id(s):
    try:
        return brickowl.canonical_id(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid order ID '{s}'")

def parse_range(s):
    """Range of local dates as (start, end) UTC Unix timestamps, end
    exclusive; None if open."""
    def day(d):
        try:
            return brickowl.parse_date(d)
        except ValueError as e:
            raise argparse.ArgumentTypeError(f"Invalid date range '{s}': {e}")

    if RANGE_SEP in s:
        start, end = (x.strip() for x in s.split(RANGE_SEP, 1))
        start = day(start) if start else None
        end = day(end) if end else None
    else:
        start = end = day(s.strip())

    if start and end and end < start:
        raise argparse.ArgumentTypeError(f"Invalid date range '{s}', end is before start")

    return (brickowl.local_day_start(start) if start else None,
            brickowl.local_day_start(end + timedelta(days=1)) if end else None)

def parse_statuses(s):
    """Set of status IDs for a comma separated list of state names or IDs,
    a '+' suffix adding greater states."""
    sids = set()
    seen = set()
    for e in s.split(','):
        e = e.strip()
        plus = e.endswith('+')
        name = e[:-1].strip() if plus else e
        try:
            sid = brickowl.status_id(name)
        except ValueError:
            sid = None
        if sid is None:
            raise argparse.ArgumentTypeError(
                f"Invalid order status list '{s}', must be states from: {', '.join(brickowl.STATUSES)}")
        if sid in seen:
            raise argparse.ArgumentTypeError(f"Invalid order status list '{s}', repeated state")
        seen.add(sid)

        if not plus:
            sids.add(str(sid))
        elif sid <= int(brickowl.STATUS_RECEIVED):
            sids.update(str(i) for i in range(sid, int(brickowl.STATUS_RECEIVED) + 1))
        else:
            sids.update((brickowl.STATUS_ON_HOLD, brickowl.STATUS_CANCELLED))
    return sids

def add_scope_arguments(parser, implicit_status=True):
    """Scope directive arguments; implicit_status per Scope."""
    status_default = ('default all but On Hold and Cancelled, unless given by --orders' if implicit_status
                      else 'default all')
    parser.add_argument('--orders', type=parse_ids, action='append', default=[],
                        help='Comma separated list of order IDs')
    parser.add_argument('--from', dest='from_ids', metavar='ID', type=parse_id, action='append', default=[],
                        help='Order ID starting a sequence of it and all orders placed at or after it')
    parser.add_argument('--in', dest='ranges', metavar='RANGE', type=parse_range, action='append', default=[],
                        help='Dates placed: DATE, START::, ::END, or START::END (inclusive); '
                             'dates YYYYMMDD, YYYY-MM-DD, or YYYY/MM/DD')
    parser.add_argument('--status', dest='statuses', metavar='STATES', type=parse_statuses,
                        action='append', default=[],
                        help='Comma separated order states, each with + for it or any later state; from '
                             f'{", ".join(brickowl.STATUSES)} ({status_default})')

# Configuration file keys for scope directives: args attribute, parser.
SCOPE_KEYS = {
    'orders': ('orders', parse_ids),
    'from': ('from_ids', parse_id),
    'in': ('ranges', parse_range),
    'status': ('statuses', parse_statuses),
}

def apply_config_scope(args, data):
    """Scope directives from configuration data, unless any given on the command line.

    Each key's value is a string or list of strings, as on the command line."""
    if any(getattr(args, dest, None) for dest, _ in SCOPE_KEYS.values()):
        return
    for key, (dest, parse) in SCOPE_KEYS.items():
        v = data.get(key)
        if v is None:
            continue
        try:
            setattr(args, dest, [parse(str(x)) for x in (v if isinstance(v, list) else [v])])
        except argparse.ArgumentTypeError as e:
            raise ValueError(f"Configuration '{key}': {e}")


class Scope:
    """Order scope from the command line directives.

    Repeats of a directive are alternatives; distinct directives must
    all be met.  With the implicit status filter, On Hold and Cancelled
    orders are only in scope if explicitly given by status or order ID."""

    def __init__(self, args, from_ts=[], implicit_status=True):
        self.ids = {o for ids in args.orders for o in ids} or None
        self.after = min(from_ts) if from_ts else None
        self.ranges = args.ranges
        # None is the implicit filter excluding On Hold and Cancelled.
        self.statuses = set().union(*args.statuses) if args.statuses else None
        self.implicit_status = implicit_status

    def list_lower(self):
        """Earliest order time that may be in scope, None if unbounded."""
        bounds = [self.after]
        if self.ranges and all(start is not None for start, _ in self.ranges):
            bounds.append(min(start for start, _ in self.ranges))
        bounds = [b for b in bounds if b is not None]
        return max(bounds) if bounds else None

    def placed_ok(self, ts):
        """Whether an order placed at ts is in scope; orders with no time
        only match if no placement directive is given."""
        if ts is None:
            return self.after is None and not self.ranges
        return ((self.after is None or ts >= self.after) and
                (not self.ranges or
                 any((start is None or ts >= start) and (end is None or ts < end)
                     for start, end in self.ranges)))

    def status_ok(self, view):
        sid = brickowl.order_status(view)
        if self.statuses is not None:
            return sid in self.statuses
        return (not self.implicit_status or self.ids is not None or
                sid not in (brickowl.STATUS_ON_HOLD, brickowl.STATUS_CANCELLED))

    def placed(self):
        """Whether any directive scopes orders by time placed."""
        return self.after is not None or bool(self.ranges)

    def matches(self, view):
        return ((self.ids is None or brickowl.canonical_id(view['order_id']) in self.ids) and
                (not self.placed() or self.placed_ok(brickowl.order_time(view))) and
                self.status_ok(view))


#-- Cache -----------------------------------------------------------------

class OrderError(Exception):
    """A cached order that cannot be read or has invalid data."""

class ScopeError(Exception):
    """A fault determining the cached orders in scope."""

def empty(v):
    return v is None or (isinstance(v, str) and not v.strip())

def money(d, field):
    """Monetary field as a Decimal, None if empty; OrderError if malformed."""
    v = d.get(field)
    if empty(v):
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        s = repr(v)
    elif isinstance(v, str):
        s = v.strip()
    else:
        s = None
    if s is None or not brickowl.NUMBER.fullmatch(s):
        raise OrderError(f"invalid {field} '{v}'")
    try:
        return Decimal(s)
    except InvalidOperation:
        raise OrderError(f"invalid {field} '{v}'")

def order_time(view):
    try:
        return brickowl.order_time(view)
    except ValueError as e:
        raise OrderError(str(e))

def order_status(view):
    try:
        return brickowl.view_status(view)
    except ValueError as e:
        raise OrderError(str(e))

def read_order(oid, fn):
    """Cached order data, its view checked to be that of the given order ID."""
    try:
        data = tjawn.loadf(fn)
    except OSError as e:
        raise OrderError(f"cannot be read: {e.strerror or e}")
    except Exception as e:
        raise OrderError(f"cannot be parsed: {e}")

    if not isinstance(data, dict) or not isinstance(data.get('view'), dict):
        raise OrderError("corrupted, missing view")
    view = data['view']

    if empty(view.get('order_id')):
        raise OrderError("missing order_id")
    try:
        vid = brickowl.canonical_id(view['order_id'])
    except ValueError:
        raise OrderError(f"invalid order_id '{view['order_id']}'")
    if vid != oid:
        raise OrderError(f"order_id '{view['order_id']}' does not match filename")
    return data

def scoped_orders(args, cache, implicit_status=True):
    """Cached orders in scope as (order ID, filename, data) tuples in
    order ID order; ScopeError if the scope cannot be determined."""
    if not path.isdir(cache):
        raise ScopeError(f"Cache folder '{cache}' does not exist or is not a folder")

    try:
        with os.scandir(cache) as entries:
            files = {m.group(1): e.path for e in entries
                     if (m := CACHE_FILE.fullmatch(e.name)) and e.is_file()}
    except OSError as e:
        raise ScopeError(f"Cache folder '{cache}' cannot be read: {e.strerror or e}")

    explicit = {o for ids in args.orders for o in ids}
    for oid in sorted(explicit | set(args.from_ids), key=int):
        if oid not in files:
            raise ScopeError(f"Order {oid} is not in the cache")

    orders = {}
    for oid in sorted(explicit | set(args.from_ids) if explicit else files, key=int):
        try:
            orders[oid] = read_order(oid, files[oid])
        except OrderError as e:
            raise ScopeError(f"Order {oid} ({files[oid]}) {e}")

    from_ts = []
    for oid in args.from_ids:
        try:
            ts = order_time(orders[oid]['view'])
        except OrderError as e:
            raise ScopeError(f"Order {oid} ({files[oid]}) {e}")
        if ts is None:
            raise ScopeError(f"Order {oid} given by --from has no order time")
        from_ts.append(ts)

    scope = Scope(args, from_ts, implicit_status)

    def in_scope(view):
        """Whether an order is in scope; OrderError if a field the scope
        depends on is malformed or unrecognized."""
        if scope.placed():
            order_time(view)
        if scope.statuses is not None:
            order_status(view)
        return scope.matches(view)

    scoped = []
    for oid, data in orders.items():
        try:
            if in_scope(data['view']):
                scoped.append((oid, files[oid], data))
        except OrderError as e:
            raise ScopeError(f"Order {oid} ({files[oid]}) {e}")
    return scoped


#-- Sorting ---------------------------------------------------------------

def natural_key(s):
    """Case-insensitive key with runs of digits compared numerically."""
    # Digit runs order as if a '0' character, then by value.
    return tuple(('0', int(t)) if '0' <= t[0] <= '9' else (t, 0)
                 for t in re.findall(r'[0-9]+|.', s.casefold(), re.S))
