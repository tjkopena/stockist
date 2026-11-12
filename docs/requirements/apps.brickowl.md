# apps.brickowl

This document provides information about the Brick Owl ecommerce site
relevant to several of the `stockist` programs.


## 1. Background Information                                 ^background

Brick Owl is a portal through which to purchase LEGO pieces and sets
from a number of independent individual stores.

Each order placed is associated with a single store.

Some uncommon nuances of the Brick Owl system include:
* Orders can include multiple line items under the same item ID and even
  the same item ID and condition, all of which are additive.
* Items are segregated by condition (New, Used, etc).
* Order IDs are not necessarily assigned in order by time placed---an
  order placed early can have a numerically greater order ID number.

### 1.1 API                                                         ^api

The Brick Owl API is documented in `docs/APIs/API Documentation - Brick
Owl.html`, a local cache of https://www.brickowl.com/api_docs

No consideration for rate limits and quotas is necessary until proven
otherwise, expected usage fits well within Brick Owl parameters.

Appropriate handling of data for GDPR compliance and other
considerations is left to the user of these tools.

### 1.2 Order IDs                                              ^order-id

Order IDs are positive integers.  The canonical form of an order ID is
its decimal digits without leading zeros, e.g., `7` for `007`.  Order
IDs from any source, i.e., user input, Brick Owl API responses, or
cached orders, are converted to canonical form; they are compared,
stored, and displayed only in that form.  Note that this means the value
returned from the Brick Owl API is rewritten to canonical form in cached
orders.  An order ID that is empty, non-numeric, or zero is invalid.

### 1.3 Order Status                                             ^status

Brick Owl orders have a status reflecting their current position within
the purchasing-to-receiving workflow.  There are nine states, each
having a numeric ID:

0. Pending
1. Payment Submitted
2. Payment Received
3. Processing
4. Processed
5. Shipped
6. Received
7. On Hold
8. Cancelled

These states are considered to form a partial ordering: On Hold and
Cancelled are separate states unto themselves with no precedence
relationship to any other.  The other seven states have an ordering
following their numeric ID:

  Pending < Payment Submitted < Payment Received < Processing \
    < Processed < Shipped < Received

`stockist` Brick Owl apps never consider On Hold or Cancelled orders
unless directed to do so, either by including those states via a
`--status` directive or by explicitly identifying an order via
`--orders`.  This is governed by the implicit status filter described
under Order Scope below.

States are referenced by their string names, in any case, with spaces,
hyphens, and underscores ignored, or by their numeric identifier.

### 1.4 Names                                                     ^names

For display and sorting purposes, store and item names have HTML
entities unescaped and then control characters stripped (both Unicode Cc
and Cf).

### 1.5 Natural Order                                     ^natural-order

A "natural order" or "natural sort" over string values is a
case-insensitive alphabetical sort with runs of digits compared
numerically.  This is the default sorting mechanism for store names,
item names, BOIDs, and Natural IDs.

### 1.6 Currencies                                             ^currency

Brick Owl orders include monetary fields that may be in a variety of
currencies.  Each order view gives two ISO 4217 currency codes:
* `base_currency`: The currency in which the store prices the order.
* `payment_currency`: The currency in which the buyer paid.

Monetary fields are denominated as follows:
* Base currency, in the order view: `ship_total`, `eu_duty`,
  `base_order_total`, `sub_total`, `final_sub_total_excluding_tax`,
  `coupon_discount`, `tax_amount`, `refund_shipping`, `refund_eu_duty`,
  `refund_adjustment`, `refund_subtotal`, and `refund_total`.
* Base currency, in each order item: `base_price`.
* Payment currency, in the order view: `payment_total`.

Other fields, e.g., `tax_rate` and `weight`, are not monetary.

Brick Owl orders cached by `stockist` have a sibling `<field>_USD`
immediately following each of the above monetary fields present in the
order, giving its value in equivalent United States dollars.  The value
is the original multiplied by a conversion rate.  An original value that
is null or the empty string is copied as is.

All monetary fields of an order are converted consistently, anchored on
the amount actually paid.

Payment currency fields are converted by the order's payment rate:
1. If `payment_currency` is USD, a rate of 1, i.e., Brick Owl's recorded
   `payment_total` is taken as the exact USD paid.
2. Otherwise the European Central Bank (ECB) reference rate from
   `payment_currency` to USD for the date the order was placed, in
   Brick Owl's timezone as given below.

Base currency fields are converted by the order's effective rate,
`payment_total_USD / base_order_total`, regardless of `base_currency`,
including when it is USD or the same as `payment_currency`.
`base_order_total_USD` is set to exactly `payment_total_USD` rather than
computed, so the two are always equal, including when
`base_order_total` is 0.  Every USD amount thus reflects the order's
portion of what was actually paid.  If `base_order_total` is 0, all
other base `*_USD` fields are set to 0, apart from null or empty
originals, which are copied as is.  An order with a missing, null, or
empty `base_order_total` or `payment_total` cannot be converted.

The date the order was placed is the calendar date of
`iso_order_time`, i.e., in Brick Owl's own timezone as given by that
timestamp's UTC offset, independent of the system performing the
conversion.  This is an exception to the UTC handling of times in
§dates:2.2.  ECB publishes rates only on its working days; for other
dates the rate of the most recent preceding working day is used.

### 1.7 Totals                                                   ^totals

The "total" of an order refers to the payment total, i.e., including
shipping and fees but subtracting refunds: `payment_total_USD -
refund_total_USD`.  An empty, null, or missing refund is considered to
be of value 0.  An empty, null, or missing `payment_total_USD` with a
non-empty and non-zero `refund_total_USD` is an error, as is a malformed
`payment_total_USD` or `refund_total_USD`.  Per the single conversion of
§currency:1.6, `payment_total_USD` and the refund fields share the same
rate basis.

### 1.8 Natural IDs                                          ^natural-id

Items in cached orders are given a Natural ID meant for human display
use.  The Natural ID for an item is assigned from the following sources
in order of preference as available and applicable:
* LEGO Set Number
* LEGO Design ID or Obsolete Design ID (deduplicated list separated by
  '/', grouped by Design IDs first and Obsolete Design IDs next, then
  ordered as given within those groups)
* LEGO Item Number
* BrickLink ID
* BOID
* Blank

### 1.9 Item Condition                                        ^condition

Brick Owl items are rated for their condition.  The ordering over
conditions from greatest to least is:

|Label             | API  |
---------------------------
|New               |new   |
|New (Complete)    |newc  |
|New (Sealed)      |news  |
|New (Incomplete)  |newi  |
|Used (Like New)   |usedn |
|Used (Good)       |usedg |
|Used (Complete)   |usedc |
|Used (Incomplete) |usedi |
|Used (Acceptable) |useda |


## 2. Common Configuration & Parameters                   ^configuration

A configuration file may be specified via the command line (`--conf`).
The default configuration file is `.conf/brickowl.jawn`.

Command line parameters take precedence over any setting specified in a
configuration file, whether the latter is default or given explicitly.

Unless explicitly stated otherwise, configuration options for specific
`stockist` Brick Owl programs may be included in configuration files.

### 2.1 Relative Paths                                            ^paths

Relative paths are resolved against the working directory.

### 2.2 Dates & Times                                             ^dates

Times are handled internally as absolute instants in UTC.  All
computations over times, e.g., comparisons, ranges, and ordering, are
made in UTC.  The instant an order was placed is given by its
`iso_order_time`.  Any time stored by `stockist`, as opposed to Brick
Owl fields cached as given, is in UTC and written as ISO 8601 text with
a `Z` suffix.

Input dates, i.e., from command line parameters or configuration files,
are accepted in either `YYYYMMDD`, `YYYY-MM-DD`, or `YYYY/MM/DD` format
and assume local system time.  Invalid calendar dates in user input are
errors.  On input, a date is converted to the span of UTC instants from
the local midnight beginning it (inclusive) to the local midnight
beginning the next day (exclusive); this span is 23 or 25 hours on days
of daylight saving transitions.

Names, labels, filenames, and other display text, including any dates
or times within them, use local system time, converted from UTC on
output.

Exceptions to the above are given explicitly where they apply, e.g., the
currency conversion date in §currency:1.6.

### 2.3 API Key                                                 ^api-key

The Brick Owl API Key to use may be specified in the configuration file
or on the command line (`--key`).  It is not required unless an
application needs to make calls to the Brick Owl API.

### 2.4 Cache                                                     ^cache

Most of the `stockist` Brick Owl apps operate over a local cache of
order data rather than using the Brick Owl API directly.  The cache
folder may be specified in the configuration file or on the command line
(`--cache`).  The default is `data/brickowl/orders/`.  The cache is
considered to be comprised only of files in the cache location with
filename matching `^order-[1-9][0-9]*\.jawn$`.  Temporary and other
files, including those named with non-canonical order IDs (e.g.,
`order-007.jawn`), are ignored for purposes of reading from the cache.
Each order thus has exactly one possible cache filename,
`order-<ID>.jawn` with the order ID in canonical form.

### 2.5 Order Scope                                         ^order-scope

The Brick Owl orders over which to operate may be scoped by several
parameters, each of which may be specified more than once:
* `--orders <IDs>`: An explicit, comma separated list of one or more
  order IDs to be included in scope.  Listed orders are exempt from the
  implicit status filter described below, but remain subject to any
  `--status` directive.  Whitespace between order IDs and commas is
  permitted.  ID lists with leading, repeated, or trailing commas; an
  empty or whitespace-only parameter; invalid order IDs; or order IDs
  repeated after conversion to canonical form (e.g., `7,007`) are
  errors.
* `--from <ID>`: An order ID identifying the start of a sequence
  including itself and every order simultaneous or subsequent by time
  placed (comparison is between UTC instants, not date-based).
* `--in <range>`: An inclusive range of local dates for which all orders
  placed on or after the start and on or before the end are included,
  compared as UTC instants per §dates:2.2, where `<range>` is specified
  by one of:
  * `<date>`: On the given date specifically.
  * `<start>::`: From the given date to the infinite future.
  * `::<end>`: From the infinite past to the given date.
  * `<start>::<end>`: From the given start date to the given end date.
    Specifying an end date before the start date is an error.
  * `::`: From the infinite past to the infinite future, redundant with
    not specifying any `--in` but permitted.
* `--status <states>`: A comma separated list of Brick Owl order states
  required of orders to be included in scope.  If a '+' suffix is
  included on an element then all orders of that state or greater are
  included.  E.g., 'Shipped+' indicates that orders in state Shipped or
  Received are to be included.  A `+` suffix on Cancelled or On Hold
  indicates inclusion of both those states, as a convenience rather than
  a reflection of any ordering between them.  `Pending+` does not
  include Cancelled or On Hold.

  Whitespace between states, suffixes, and commas is permitted.  States
  lists with leading, repeated, or trailing commas; an empty or
  whitespace-only parameter; repeated or unrecognized states; or
  unrecognized suffixes are errors.

Orders with no `iso_order_time` do not match `--from` or `--in`
directives and result in an error if used as the `--from` reference.

Orders with no `status` do not match `--status` directives.

Repeated scope directives of the same type are disjunctive; the set of
orders to work with is the union of the criteria.  E.g., specifying
`--orders 1234 --orders 5678` is equivalent to `--orders 1234,5678`.

Scope directives of different type are conjunctive; the set of orders to
work with is the intersection of the specified criteria.  E.g.,
specifying a date range as well as a set of order IDs results in the
subset of that explicit list which falls within the date range.

When no `--status` directive is given, an implicit status filter
excludes On Hold and Cancelled orders, except orders named in
`--orders`.  Orders with no status pass this filter.  Like other
directives, this filter is conjunctive with the rest of the scope.
E.g., a Cancelled order used as the `--from` reference is not itself
included unless it is also named in `--orders`.

The default scope if no directive is given is all orders, subject to the
implicit status filter.

If any scope directive is given on the command line, all scope
directives in the configuration file are discarded.

Any error in accessing an order to determine its inclusion in the order
scope aborts the run with an error, including:
* Cache location doesn't exist or is not a folder.
* Explicit order ID given in `--from` or `--orders` scope doesn't exist.
* Order file cannot be read.
* Order file is corrupted, e.g., either unparseable or missing `view`.
* A missing or invalid order ID, or one whose canonical form differs
  from the order ID in the filename.
* An unrecognized status ID or string if any explicit `--status`
  directive is to be applied.
