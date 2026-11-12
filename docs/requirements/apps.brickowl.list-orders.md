# Brick Owl: apps.brickowl.list-orders

This document outlines `apps.brickowl.list-orders`, a command line
program for reporting basic information about cached orders.  It is part
of the overall `stockist` collection of tools for working with several
specific niche ecommerce stores and suppliers.

This application inherits background information, features, and
requirements from the `apps.brickowl.md` document.


## 1. Functional Overview

`apps.brickowl.list-orders` prints to the console basic information
about cached orders in scope.


## 2. Configuration & Parameters

`apps.brickowl.list-orders` has the following command-line-only
configuration options beyond those in the inherited `apps.brickowl.md`:
* `--csv`: A flag to format the output as CSV.
* `--sort <criteria>`: Specifies the sequence of sortings to apply over
  the displayed orders. `criteria` is a comma separated list of one or
  more of the following tags indicating a particular aspect:
  * `id`: The order's ID number (numeric sort; default `desc`).
  * `time`: UTC instant the order was placed (time sort; default
    `desc`).
  * `date`: Local system date the order was placed (date sort; default
    `desc`).
  * `store`: Name of the Brick Owl store to which the order was placed
    (§apps.brickowl.md:names; ties broken by ascending store ID
    regardless of the name sorting direction; default `asc`).
  * `status`: Sort over order states following the partial ordering
    defined in `apps.brickowl.md` (default `asc`); On Hold and then
    Cancelled are considered to always sort after the other statuses
    regardless of the sort direction (`asc` or `desc`).
  * `total`: The order total (numeric sort over the value to two decimal
    places rounded half-away-from-zero; default `desc`).

  Optional `:asc` and `:desc` suffixes on each element control whether
  the sort follows natural ordering (`:asc`) or its reverse (`:desc`).

  Defaults and tiebreakers are appended to the sort specification:
  * If `id` was specified, whether or not `time` was specified, no
    further action is needed as IDs are a unique total ordering.
  * If `time` was specified, `id` is appended to the sort specification.
  * If neither `id` nor `time` was specified, `time` and then `id` are
    appended to the sort specification.

  The sort direction of these appended specifications follow that of the
  last (rightmost) explicitly given `date` or `time` sorting tag
  appearance and otherwise their default.

  Note these rules for appending specifications make `time,id` the
  default when no `--sort` is given.

  Sort tags and suffixes are case-insensitive.  Whitespace between tags,
  directions, colons, and commas is permitted.  Sort criteria with
  leading, repeated, or trailing commas; an empty or whitespace-only
  parameter; repeated or unrecognized tags; or unrecognized sorting
  directions are errors.  Repeated `--sort` options are an error.

  Missing values sort last regardless of sort direction.

  Sort criteria examples:
  * `date,total`: Group orders by date placed then list by total.
  * `status,time`: Group orders by status and then timestamp
  * `time:asc`: List orders from oldest to newest.


## 3. Function

Report output is sent to stdout.

A header row with column labels is printed first.

A row is then printed for each order within scope in the cache:
* Order ID (left justified)
* Order Time (YYYY-MM-DD HH:MM, 24hr; left justified)
* Store ID (left justified)
* Store Name (whitespace trimmed; left justified)
* Total (USD; '$' sign, two decimals rounded half-away-from-zero, no
  thousands separator, negative values in form -$0.00; right justified)
* Status (label; left justified)

No output line has trailing whitespace.

Missing field data, e.g., an order without a total, prints as blank.

If `--csv` is given they are printed as comma-separated quoted elements
with no extra whitespace (including the header labels), except Total
which is given as a number (with two decimal places rounded
half-away-from-zero).  Quotes are escaped by doubling and lines end with
just a linefeed.

Otherwise the output uses spaces to justify each element within a fixed
width column.  Column widths are calculated to be the greatest display
width for values of that column.  The header labels are justified the
same as their values and included in column width calculation.  An
additional separating space is included between each column.

If no orders are in scope the header prints and the run exits 0.

No differentiation is made between output to a terminal or otherwise.


## 4. Incorrect, Missing, and Inaccessible Data

Empty, null, or missing fields other than order ID are not an error
unless entailed otherwise (e.g., missing `iso_order_time` in an order
used as a `--from` scope reference).

Non-empty but invalid data in a field included in the report output is a
terminating error.
