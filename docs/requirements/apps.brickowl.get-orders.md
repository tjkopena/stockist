# Brick Owl: apps.brickowl.get-orders

This document outlines `apps.brickowl.get-orders`, a command line
program for downloading orders from the Brick Owl ecommerce site.  It is
part of the overall `stockist` collection of tools for working with
several specific niche ecommerce stores and suppliers.

This application inherits background information, features, and
requirements from the `apps.brickowl.md` document.


## 1. Functional Overview                                      ^overview

`apps.brickowl.get-orders` downloads orders from Brick Owl and caches
them locally as individual files for later processing and analysis.  It
works with buyer orders, i.e., purchases made by the Brick Owl user
associated with the configured API key.  Orders already cached are only
downloaded again, and their files overwritten, if Brick Owl reports them
updated since they were last confirmed current.

## 2. Configuration & Parameters                          ^configuration

In the context of `apps.brickowl.get-orders`, the order scope directives
are interpreted as defining those orders to be downloaded.  Its scope is
evaluated solely against the API, not any cached orders; which orders in
scope are actually downloaded additionally depends on the cache and the
cache log (§freshness:3.3).  Local input dates are converted for the
API's `iso_order_time` filter and for comparisons, per
§apps.brickowl.md:dates:2.2.

The cache folder (§apps.brickowl.md:cache:2.4) is the target location to
which the downloaded orders are to be written.

`apps.brickowl.get-orders` has the following configuration options
beyond those in the inherited `apps.brickowl.md`:
* `--force`: Download all orders in scope regardless of freshness
  (§freshness:3.3).  This option is command line only; it may not be set
  in a configuration file.
* `--cache-log <file>`: The file recording when each cached order was
  last confirmed current (§cache-log:3.3.1).  It may also be set in the
  configuration file as `cache_log`.  The default is `.get-orders.jawn`
  within the cache folder.  An explicitly given relative path is resolved
  against the working directory per §apps.brickowl.md:paths:2.1, not
  against the cache folder.

## 3. Function                                                 ^function

### 3.1 Mode                                                       ^mode

This app operates over orders sent by the user as a purchaser---buyer
orders accessed via "customer" mode in Brick Owl API terms.  This is
different from the API default of vendor orders received as a seller.
Orders included via explicit IDs in any scope directive are not checked
to confirm their mode (buyer or seller).

### 3.2 Downloads                                             ^downloads

An "order" here is considered to comprise both the order details (Brick
Owl's `order/view` endpoint) and the order's line items (Brick Owl's
`order/items` endpoint).  These are retrieved and cached together.

All orders matching the directed scope are downloaded unless they are
current (§freshness:3.3).  In an exception to
§apps.brickowl.md:order-scope:2.5, `apps.brickowl.get-orders` implicitly
includes On Hold and Cancelled orders in scope.  Explicit `--status`
directives follow §apps.brickowl.md:order-scope:2.5.

### 3.3 Freshness                                             ^freshness

An order in scope is "current", and is not downloaded, if its cached
copy is known to reflect Brick Owl's present data for it.  Freshness is
determined per order, independent of the scope directives used in any
run, from the cache log and Brick Owl's record of when each order was
last updated.

An order can only be current if it is "known": It has a cache file that
can be read, parses, has a `view`, and has an order ID matching its
filename; and it has an entry in the cache log.  Orders that are not
known, e.g., never downloaded, their cache file deleted or corrupted, or
downloaded with a different cache log, are always downloaded.  A cache
file that is unreadable or corrupted is not an error here; the order is
downloaded and the file overwritten.

With `--force` the cache log is not read, no order is current, and every
order in scope is downloaded.  The cache log is still updated at the end
of the run (§cache-log:3.3.1).

Freshness relies on Brick Owl advancing an order's `updated_time` (in
the order view) whenever the order view or its items change.  This is
confirmed for status changes and assumed otherwise.  Data computed by
`apps.brickowl.get-orders` itself, e.g., Natural IDs (§natural-id:3.6)
from Brick Owl catalog data, are not reflected in `updated_time`;
refreshing those requires `--force`.

#### 3.3.1 Cache Log                                          ^cache-log

The cache log is a Jawn map from order IDs, in canonical form, to the
time at which that order's cached copy was last confirmed current,
stored as ISO 8601 UTC text per §apps.brickowl.md:dates:2.2.  Any other
content, e.g., a value that is not a map, a key that is not a canonical
order ID, or a value that is not a valid time, makes the log corrupted.

A missing cache log is equivalent to an empty one.

The run start time is the time immediately before the first Brick Owl
API call of the run.  At the conclusion of the execution phase
(§execution-errors:4.3), including when individual orders were flagged,
the cache log is written with entries updated as follows:
* Orders written to the cache with no faults, and orders determined to
  be current, are given the run start time.
* Orders written to the cache despite Natural ID lookup faults
  (§natural-id:3.6) have their entry removed, so that they are
  downloaded again on the next run.
* Orders not written for any reason, e.g., flagged or found to be out of
  scope once their view is retrieved, keep their existing entry, if any.
* Entries for all other orders are kept as read at the start of the run.
  With `--force`, they are kept if the existing log can be read, and
  otherwise discarded with a warning.

A run terminated before the conclusion of the execution phase does not
update the cache log; orders it wrote are downloaded again next run.

If the cache log's folder does not exist, it and any necessary parent
folders are created when the log is written.  The log is written
atomically, i.e., as a temp file that is then renamed.  Failure to
create the folder or write the log is flagged to the user, and the run
concludes as a failure, but already written orders are kept.

Concurrent runs over the same cache or cache log are not supported.
Whichever run writes the log last determines its content; as every entry
records a time its order was genuinely confirmed current, the worst
consequence is orders being downloaded again unnecessarily.

#### 3.3.2 Orders Listed by Brick Owl                            ^listed

When the scope does not name orders explicitly via `--orders`, orders in
scope are determined from Brick Owl's `order/list` endpoint as described
in §downloads:3.2.  Freshness is then determined as follows:
1. If none of the listed orders in scope are known, all are downloaded.
2. Otherwise, the earliest cache log time among those known orders, less
   a margin of one hour, is used as the `update_time` filter for a
   second `order/list` call, with the same `list_type` and `order_time`
   arguments as the first.  The margin absorbs any difference between
   the local system clock and Brick Owl's.
3. Known orders not returned by that second call have not been updated
   since their cached copy was confirmed current; they are current and
   are not downloaded.  All other listed orders in scope are downloaded.

#### 3.3.3 Orders Given Explicitly                             ^explicit

When the scope names orders explicitly via `--orders`, each order's view
is already retrieved to determine its scope.  A known order is current
if both its retrieved view and its cached view have a non-empty
`updated_time` and the two are equal.  Its `order/items` are then not
retrieved and its cache file is not rewritten.  All other orders in
scope are downloaded.

### 3.4 Canonical Order ID                                     ^order-id

`apps.brickowl.get-orders` is responsible for computing and rewriting
canonical order IDs in the cached data (§apps.brickowl.md:order-id:1.2).

### 3.5 Currency Conversion                                    ^currency

`apps.brickowl.get-orders` is responsible for computing and inserting
the `*_USD` fields shadowing monetary fields, following the fields and
conversion rules given in §apps.brickowl.md:currency:1.6.

ECB reference rates are obtained from the Frankfurter service
(https://api.frankfurter.dev/v1), which requires no API key.  Rates are
requested only for payment currencies other than USD.  Each distinct
currency and date is requested at most once per run.

An order for which any `*_USD` field cannot be computed is flagged to
the user and not written to the cache folder, but does not terminate
the run.  This includes:
* A non-null, non-empty, and non-numeric value in any monetary field.
* A missing or malformed `payment_total` or `base_order_total`.
* A missing `payment_currency`.
* A failed or invalid rate service response when needed, e.g., for a
  currency for which ECB publishes no rate.
* A missing or malformed `iso_order_time` when `payment_currency` is
  not USD.

Null-valued or empty `payment_total` or `base_order_total` fields are
treated the same as if the field were missing.

### 3.6 Natural IDs                                          ^natural-id

`apps.brickowl.get-orders` is responsible for computing and inserting
the Natural ID for items, following §apps.brickowl.md:natural-id:1.8.
It is written to each item as the field `natural_id`, immediately
following the item's `boid`.  Any source with multiple values is given
as a deduplicated list separated by '/', as for design IDs.

BrickLink IDs are not included in order items and are looked up from the
Brick Owl API's `catalog/id_list` endpoint, by the item's BOID and
otherwise its BOID without color suffix (the trailing "-[0-9]+").  Each
item type is requested at most once per run, and only if an item of that
type requires it.  Items without a BOID or of a type the endpoint
doesn't support skip this lookup.  Any errors in looking up BrickLink
IDs are flagged but do not terminate the run or processing of the order.

### 3.7 Output                                                   ^output

If the cache location already exists but is not a folder, the run
terminates in an error before any processing.

If the cache folder does not exist, whether explicitly given or the
default, it and any necessary parent folders are created by the app
(this is an exception for this app to the general stipulation that a
missing cache folder is an error).  Failure to create the folder or
folders is a fatal error.

Downloaded orders are each written as a Jawn object to its own file in
the cache folder.  The filename is the prefix "order-" then the order ID
in canonical form (§apps.brickowl.md:order-id:1.2) and ".jawn"
extension.  Any existing file of the same name in the cache folder is
overwritten.  Other files in the cache folder, apart from the cache log
when it is located there (§cache-log:3.3.1), are left alone.

The Jawn files are structured as a map `{view, items}` and otherwise
utilize the API response keys and structure.

A best effort is made to clean up temp files on conclusion or
termination of a run and they are given filenames distinctly
differentiating them from saved orders.


## 4. Incorrect, Missing, and Inaccessible Data                  ^errors

`apps.brickowl.get-orders` is divided into three phases for purposes of
error handling: Configuration, Scope Construction, and Execution.

### 4.1 Configuration                              ^configuration-errors

An unconfigured API key is a fatal error.

A cache log location that exists but is not a file, e.g., a folder, is a
fatal error, including with `--force`.

### 4.2 Scope Construction                                 ^scope-errors

Any error in accessing data necessary to instantiate the scope of orders
to download results in the run being aborted and no changes being made
to the cache folder (including folder creation) or the cache log.  This
includes:
* A cache log that exists but cannot be read, or is corrupted
  (§cache-log:3.3.1).  Not applicable with `--force`, under which the
  log is not read at this point.
* A failed `order/list` call, including the second call filtering by
  `update_time` (§listed:3.3.2).

If the constructed scope is empty the app exits with no further work and
no changes, including to the cache log.  If orders are in scope but all
are current (§freshness:3.3), none are downloaded but the run proceeds
to the execution phase to update the cache log.

### 4.3 Execution                                      ^execution-errors

After scope is established, the subsequent run is best effort unless
particular faults are specifically stated to be fatal.  Errors accessing
particular orders, converting currencies, natural ID lookup faults, or
writing outputs are flagged to the user but the run is not terminated
and successfully downloaded orders are written to the cache.

Orders only partially retrieved, i.e., either the `order/view` or
`order/items` calls fail, are flagged to the user and are not written to
the cache folder but do not terminate the run.

Orders are written to the cache folder atomically, i.e., as a temp file
that is then renamed.
