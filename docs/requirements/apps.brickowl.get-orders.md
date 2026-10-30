# Brick Owl: apps.brickowl.get-orders

This document outlines `apps.brickowl.get-orders`, a command line
program for downloading orders from the Brick Owl ecommerce site.  It is
part of the overall `stockist` collection of tools for working with
several specific niche ecommerce stores and suppliers.

This application inherits background information, features, and
requirements from the `apps.brickowl.md` document.


## 1. Functional Overview

`apps.brickowl.get-orders` downloads orders from Brick Owl and caches
them locally as individual files for later processing and analysis.  It
works with buyer orders, i.e., purchases made by the Brick Owl user
associated with the configured API key.

## 2. Configuration & Parameters

`apps.brickowl.get-orders` has the following configuration options in
addition to those in the inherited apps.brickowl.md§config.

### 2.1 Order Collection

The collection of orders to download may be scoped by a combination of
command line directives, each of which may be specified more than once:
* `--orders <IDs>`: An explicit, comma separated list of one or more
  order IDs to be included in scope.
* `--from <ID>`: An order ID identifying the start of a sequence
  including itself and every order simultaneous or subsequent by
  creation time (orders earlier in the same day are not included).
* `--in <range>`: An inclusive date range for which all orders placed on
  or after the start and on or before the end are included, where
  `<range>` is specified by one of:
  * `<date>`: On the given date specifically.
  * `<start>::`: From the given date to the infinite future.
  * `::<end>`: From the infinite past to the given date.
  * `<start>::<end>`: From the given start date to the given end date.
    Specifying an end date before the start date is an error.

The scope directives are additive; the set of orders to download is the
union of the specified criteria.  E.g., specifying a date range as well
as a list of order IDs results in every order within that date range
being collected as well as all orders in the enumerated list, each
member of which may or may not fall into the date range.

If no scope directive is given, all orders are to be downloaded.

### 2.2 Output

A file system folder may be specified as the target for outputting the
downloaded orders (`--out`).  The default is `data/brickowl/orders/`.


## 3. Function

### 3.1 Mode

This app operates over orders sent by the user as a purchaser---buyer
orders accessed via "customer" mode in Brick Owl API terms.  This is
different from the API default of vendor orders received as a seller.
Orders included via explicit IDs in any scope directive are not checked
to confirm their mode (buyer or seller).

### 3.2 Incorrect, Missing, and Inaccessible Data

Any error in accessing data necessary to instantiate the scope of orders
to download results in the run being aborted and no changes being made
to the target folder.  This includes:
* A `--from` scope directive is given but the given order ID starting
  the sequence cannot be accessed.
* An API call to `order/list` fails.

Once the scope is established, the subsequent run is best effort.
Errors accessing particular orders or writing outputs are flagged to the
user but the run is not terminated and successfully downloaded orders
are written to the target folder.

Orders only partially retrieved, i.e., only one of the `order/view` and
`order/items` components is retrieved, are flagged to the user and are
not written to the target folder but do not terminate the run.

Orders are written to the target folder atomically, i.e., as a temp file
that is then renamed.

### 3.3 Downloads

An "order" here is considered to comprise both the order details (Brick
Owl's `order/view` endpoint) and the order's line items (Brick Owl's
`order/items` endpoint).  These are retrieved and cached together.

All orders matching the directed scope are downloaded, regardless of
status (i.e., cancelled orders are included).

### 3.4 Output

If the output target folder does not exist, whether explicitly given or
the default, it is created by the app.  The existence of that folder as
a file is an error that terminates the run.

Downloaded orders are each written as a Jawn object to its own file in
the target folder.  The filename is the order ID with the ".jawn"
extension.  Any existing file of the same name in the target folder is
overwritten.  Other files existing in the target folder are left alone.

The Jawn files are structured as a map `{view, items}` and otherwise
utilize the API response keys and structure.

A best effort is made to clean up temp files on conclusion or
termination of a run and they are given filenames distinctly
differentiating them from saved orders.
