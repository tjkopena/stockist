if __name__ != '__main__':
    raise Error("This is a script, not intended to be imported")

from datetime import timedelta
from os import path
import argparse
import os
import signal
import sys
import tempfile

from stockist import brickowl

import logberry
import tjawn


RANGE_SEP = '::'
TEMP_PREFIX = '.get-orders-'
TEMP_SUFFIX = '.tmp'


def parse_ids(s):
    ids = [o.strip() for o in s.split(',') if o.strip()]
    if not ids or not all(o.isdigit() for o in ids):
        raise argparse.ArgumentTypeError(f"Invalid order ID list '{s}'")
    return ids

def parse_id(s):
    if not s.strip().isdigit():
        raise argparse.ArgumentTypeError(f"Invalid order ID '{s}'")
    return s.strip()

def parse_range(s):
    """Range as (start, end) Unix timestamps, end exclusive; None if open."""
    def day(d):
        try:
            return brickowl.parse_date(d)
        except ValueError as e:
            raise argparse.ArgumentTypeError(str(e))

    if RANGE_SEP in s:
        start, end = (x.strip() for x in s.split(RANGE_SEP, 1))
        if not start and not end:
            raise argparse.ArgumentTypeError(f"Invalid date range '{s}', no dates given")
        start = day(start) if start else None
        end = day(end) if end else None
    else:
        start = end = day(s.strip())

    if start and end and end < start:
        raise argparse.ArgumentTypeError(f"Invalid date range '{s}', end is before start")

    return (int(start.timestamp()) if start else None,
            int((end + timedelta(days=1)).timestamp()) if end else None)


parser = argparse.ArgumentParser(prog='python -m apps.brickowl.get-orders',
                                 description='Download Brick Owl purchase orders into a local cache folder')
parser.add_argument('--key', help='Brick Owl API key (default from configuration file)')
parser.add_argument('--conf', default='.conf/brickowl.jawn', help='Configuration file (default .conf/brickowl.jawn)')
parser.add_argument('--orders', type=parse_ids, action='append', default=[],
                    help='Comma separated list of order IDs')
parser.add_argument('--from', dest='from_ids', metavar='ID', type=parse_id, action='append', default=[],
                    help='Order ID starting a sequence of it and all orders placed at or after it')
parser.add_argument('--in', dest='ranges', metavar='RANGE', type=parse_range, action='append', default=[],
                    help='Dates placed: DATE, START::, ::END, or START::END (inclusive); '
                         'dates YYYYMMDD, YYYY-MM-DD, or YYYY/MM/DD')
parser.add_argument('--out', default='data/brickowl/orders', help='Output folder (default data/brickowl/orders)')
args = parser.parse_args()


def abort(msg, **kwargs):
    logberry.error(msg, **kwargs)
    logberry.stop()
    sys.exit(1)

def on_sigterm(signum, frame):
    sys.exit(128 + signum)

signal.signal(signal.SIGTERM, on_sigterm)

logberry.start()

if path.exists(args.out) and not path.isdir(args.out):
    abort("Output folder exists as a file", out=args.out)


#-- Scope -----------------------------------------------------------------

explicit = [o for ids in args.orders for o in ids]
scoped = bool(explicit or args.from_ids or args.ranges)

try:
    settings = brickowl.Settings(api_key=args.key) if args.key else brickowl.load_configuration(args.conf)
    api = brickowl.client(settings)

    from_ts = [int(api.view_order(oid)['order_time']) for oid in args.from_ids]

    listed = []
    if not scoped or from_ts or args.ranges:
        if not scoped or any(start is None for start, _ in args.ranges):
            lower = None
        else:
            lower = min(from_ts + [start for start, _ in args.ranges])

        def in_scope(ts):
            return (not scoped or
                    any(ts >= f for f in from_ts) or
                    any((start is None or ts >= start) and (end is None or ts < end)
                        for start, end in args.ranges))

        listed = [o['order_id'] for o in api.list_orders(order_time=lower)
                  if in_scope(int(o['order_date']))]

except Exception as e:
    abort("Could not establish order scope", error=str(e))

order_ids = list(dict.fromkeys(listed + explicit))


#-- Download --------------------------------------------------------------

def write_order(oid, order):
    fd, tmp = tempfile.mkstemp(dir=args.out, prefix=TEMP_PREFIX, suffix=TEMP_SUFFIX)
    try:
        with os.fdopen(fd, "wt") as f:
            f.write(tjawn.dumps(order))
        os.replace(tmp, path.join(args.out, f"{oid}.jawn"))
    finally:
        if path.exists(tmp):
            os.remove(tmp)

t = logberry.task("Download orders", orders=len(order_ids), out=args.out)
written = 0
flagged = []

try:
    os.makedirs(args.out, exist_ok=True)

    for oid in order_ids:
        try:
            view = api.view_order(oid)
        except Exception as e:
            t.warning("Order not accessible", order_id=oid, error=str(e))
            flagged.append(oid)
            continue

        try:
            items = api.order_items(oid)
        except Exception as e:
            t.warning("Order partially retrieved, not written", order_id=oid, error=str(e))
            flagged.append(oid)
            continue

        try:
            write_order(oid, {'view': view, 'items': items})
            written += 1
        except Exception as e:
            t.warning("Could not write order", order_id=oid, error=str(e))
            flagged.append(oid)

except BaseException as e:
    t.end_failure("Run terminated", written=written, error=str(e) or type(e).__name__)
    logberry.stop()
    if isinstance(e, KeyboardInterrupt):
        sys.exit(130)
    raise

if flagged:
    t.end_failure("Some orders not downloaded", written=written, flagged=len(flagged),
                  order_ids=','.join(flagged))
else:
    t.end_success(written=written)

logberry.stop()
sys.exit(1 if flagged else 0)
