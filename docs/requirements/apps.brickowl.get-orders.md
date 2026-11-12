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
associated with the configured API key.

## 2. Configuration & Parameters                          ^configuration

`apps.brickowl.get-orders` has no configuration options beyond those in
the inherited `apps.brickowl.md`.

In the context of `apps.brickowl.get-orders`, the order scope directives
are interpreted as defining those orders to be downloaded.  Its scope is
evaluated solely against the API, not any cached orders.  Local input
dates are converted for the API's `iso_order_time` filter and for
comparisons, per §apps.brickowl.md:dates:2.2.

The cache folder is the target location to which the downloaded orders
are to be written.

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

All orders matching the directed scope are downloaded.  In an exception
to §apps.brickowl.md:order-scope:2.5, `apps.brickowl.get-orders`
implicitly includes On Hold and Cancelled orders in scope.  Explicit
`--status` directives follow §apps.brickowl.md:order-scope:2.5.

### 3.3 Canonical Order ID                                     ^order-id

`apps.brickowl.get-orders` is responsible for computing and rewriting
canonical order IDs in the cached data (§apps.brickowl.md:order-id:1.2).

### 3.4 Currency Conversion                                    ^currency

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

### 3.5 Natural IDs                                          ^natural-id

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

### 3.6 Output                                                   ^output

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
overwritten.  Other files in the cache folder are left alone.

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

### 4.2 Scope Construction                                 ^scope-errors

Any error in accessing data necessary to instantiate the scope of orders
to download results in the run being aborted and no changes being made
to the cache folder (including folder creation).

If the constructed scope is empty the app exits with no further work.

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
