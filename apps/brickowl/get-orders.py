if __name__ != '__main__':
    raise Error("This is a script, not intended to be imported")

from os import path
import argparse
import os
import signal
import sys
import tempfile

from apps.brickowl import common
from stockist import brickowl

import logberry
import tjawn


TEMP_PREFIX = '.get-orders-'
TEMP_SUFFIX = '.tmp'


parser = argparse.ArgumentParser(prog='python -m apps.brickowl.get-orders',
                                 description='Download Brick Owl purchase orders into a local cache folder')
common.add_config_arguments(parser)
common.add_scope_arguments(parser, implicit_status=False)
args = parser.parse_args()


def abort(msg, **kwargs):
    logberry.error(msg, **kwargs)
    logberry.stop()
    sys.exit(1)

def on_sigterm(signum, frame):
    sys.exit(128 + signum)

signal.signal(signal.SIGTERM, on_sigterm)

logberry.start()

try:
    settings = common.load_settings(args)
except Exception as e:
    abort("Could not load configuration", error=str(e))

if not settings.api_key:
    abort("No Brick Owl API key; give --key or set api_key in the configuration file")

cache = settings.cache
if path.exists(cache) and not path.isdir(cache):
    abort("Cache folder exists as a file", cache=cache)


#-- Scope -----------------------------------------------------------------

# Order views retrieved so far, by canonical order ID.
retrieved = {}

def view_order(oid):
    """Order view, checked to be the requested order and with its order
    ID rewritten to canonical form."""
    if oid not in retrieved:
        view = api.view_order(oid)
        if brickowl.canonical_id(view.get('order_id')) != oid:
            raise brickowl.APIError(f"order/view: returned order {view.get('order_id')}")
        view['order_id'] = oid
        retrieved[oid] = view
    return retrieved[oid]

def in_scope(view):
    """Whether a retrieved order is in scope; ValueError if a field the
    scope depends on is malformed or unrecognized."""
    if scope.after is not None or scope.ranges:
        brickowl.order_time(view)
    if scope.statuses is not None:
        brickowl.view_status(view)
    return scope.matches(view)

def from_time(oid):
    try:
        ts = brickowl.order_time(view_order(oid))
    except Exception as e:
        abort("Order given by --from not retrievable", order_id=oid, error=str(e))
    if ts is None:
        abort("Order given by --from has no order time", order_id=oid)
    return ts

def explicit_ok(oid):
    """Whether an order given by --orders is in scope.  These must all be
    retrievable, so are checked here where a failure aborts the run
    before anything is written."""
    try:
        return in_scope(view_order(oid))
    except Exception as e:
        abort("Order not retrievable", order_id=oid, error=str(e))

def listed_ok(o):
    """Whether a listed order may be in scope by its listed time and
    status; those without a usable time or status are decided once their
    view is retrieved."""
    try:
        ts = brickowl.parse_timestamp(o.get('order_date'), 'order_date')
        if ts is not None and not scope.placed_ok(ts):
            return False
    except ValueError:
        pass
    if scope.statuses is not None:
        try:
            sid = brickowl.view_status(o)
            if sid is not None and str(sid) not in scope.statuses:
                return False
        except ValueError:
            pass
    return True

def listed_id(o):
    try:
        return brickowl.canonical_id(o.get('order_id'))
    except ValueError:
        abort("Order listed with invalid ID", order_id=str(o.get('order_id')))

try:
    api = brickowl.client(settings)

    from_ts = [from_time(oid) for oid in args.from_ids]
    scope = common.Scope(args, from_ts, implicit_status=False)

    if scope.ids is not None:
        order_ids = [oid for oid in dict.fromkeys(o for ids in args.orders for o in ids)
                     if explicit_ok(oid)]
    else:
        order_ids = list(dict.fromkeys(listed_id(o)
                                       for o in api.list_orders(order_time=scope.list_lower())
                                       if listed_ok(o)))

except Exception as e:
    abort("Could not establish order scope", error=str(e))

if not order_ids:
    logberry.info("No orders in scope")
    logberry.stop()
    sys.exit(0)


#-- Download --------------------------------------------------------------

class Fatal(Exception):
    pass

def make_cache():
    """Create the cache folder if needed, only once there is an order to
    write; failure is fatal."""
    try:
        os.makedirs(cache, exist_ok=True)
    except Exception as e:
        raise Fatal(f"Could not create cache folder '{cache}': {e}")

def write_order(oid, order):
    make_cache()
    fd, tmp = tempfile.mkstemp(dir=cache, prefix=TEMP_PREFIX, suffix=TEMP_SUFFIX)
    os.close(fd)
    try:
        tjawn.dumpf(order, tmp)
        os.replace(tmp, path.join(cache, f"order-{oid}.jawn"))
    finally:
        if path.exists(tmp):
            os.remove(tmp)

natural_ids = brickowl.NaturalIDs(api)

t = logberry.task("Download orders", orders=len(order_ids), cache=cache)
written = 0
skipped = 0
# Orders not written, and orders written despite Natural ID lookup faults.
flagged = []
faulted = []

try:
    for oid in order_ids:
        try:
            view = view_order(oid)
        except Exception as e:
            t.warning("Order not accessible", order_id=oid, error=str(e))
            flagged.append(oid)
            continue

        try:
            ok = in_scope(view)
        except ValueError as e:
            t.warning("Order scope undeterminable, not written", order_id=oid, error=str(e))
            flagged.append(oid)
            continue
        if not ok:
            t.info("Order out of scope, skipped", order_id=oid, status=view.get('status'))
            skipped += 1
            continue

        try:
            items = api.order_items(oid)
        except Exception as e:
            t.warning("Order partially retrieved, not written", order_id=oid, error=str(e))
            flagged.append(oid)
            continue

        try:
            items = [{**i, 'order_id': oid} if 'order_id' in i else i for i in items]
        except Exception as e:
            t.warning("Order items malformed, not written", order_id=oid, error=str(e))
            flagged.append(oid)
            continue

        try:
            view, items = brickowl.add_usd(view, items)
        except Exception as e:
            t.warning("Could not convert currency, not written", order_id=oid,
                      base_currency=view.get('base_currency'),
                      payment_currency=view.get('payment_currency'), error=str(e))
            flagged.append(oid)
            continue

        lookup_faults = []
        try:
            items = brickowl.add_natural_ids(items, natural_ids,
                                             lambda i, e: lookup_faults.append((i.get('boid'), e)))
        except Exception as e:
            t.warning("Could not determine Natural IDs, not written", order_id=oid, error=str(e))
            flagged.append(oid)
            continue
        if lookup_faults:
            t.warning("BrickLink ID lookup failed, Natural IDs fall back to BOID", order_id=oid,
                      boids=','.join(dict.fromkeys(str(b) for b, _ in lookup_faults)),
                      error=str(lookup_faults[0][1]))
            faulted.append(oid)

        try:
            write_order(oid, {'view': view, 'items': items})
            written += 1
        except Fatal:
            raise
        except Exception as e:
            t.warning("Could not write order", order_id=oid, error=str(e))
            flagged.append(oid)

except BaseException as e:
    t.end_failure("Run terminated", written=written, skipped=skipped, error=str(e) or type(e).__name__)
    logberry.stop()
    if isinstance(e, KeyboardInterrupt):
        sys.exit(130)
    if isinstance(e, Fatal):
        sys.exit(1)
    raise

if flagged or faulted:
    t.end_failure("Some orders not downloaded or with faults", written=written, skipped=skipped,
                  flagged=len(flagged), order_ids=','.join(flagged),
                  faulted=len(faulted), faulted_ids=','.join(faulted))
else:
    t.end_success(written=written, skipped=skipped)

logberry.stop()
sys.exit(1 if flagged or faulted else 0)
