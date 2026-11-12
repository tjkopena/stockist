# Brick Owl: apps.brickowl.summarize-orders

This document outlines `apps.brickowl.summarize-orders`, a command line
program for parsing and aggregating cached orders from the Brick Owl
ecommerce site into a spreadsheet workbook.  It is part of the overall
`stockist` collection of tools for working with several specific niche
ecommerce stores and suppliers.

This application inherits background information, features, and
requirements from the `apps.brickowl.md` document.


## 1. Functional Overview                                      ^overview

`apps.brickowl.summarize-orders` works over a cache of Brick Owl orders
in local files, i.e., downloaded using `apps.brickowl.get-orders`.  It
generates a spreadsheet workbook with one sheet summarizing all of the
items purchased and subsequent sheets presenting each order.  Scope
criteria can be used to constrain the report to a subset of the cache.

### 1.1 Terms                                                     ^terms

The adjusted price for an item reflects its additional cost when
shipping and other fees are considered.  It is calculated as the item's
portion of the total actually paid (§apps.brickowl.md:totals:1.7), with
the portion calculated as its fraction of the order subtotal.  The order
subtotal is computed from the order's line items as the sum of each
item's `base_price_USD` times its net-of-refund quantity
(`ordered_quantity` minus `refunded_quantity`), not including shipping
and other fees; the view's `sub_total` field is not used.  An adjusted
subtotal is a sum of the adjusted prices for a given item, whether that
is an order line item or a BOID aggregate.  E.g.:
- An order has a subtotal of $20 and a total payment of $25
- The order includes two line items:
  - 10x Part 1234 priced at $1 each
  - 20x Part 5678 priced at $0.5 each
- Calculations for Part 1234:
  - The subtotal for all ten Parts 1234 is therefore $1*10 = $10
  - The portion of the total paid is therefore 10/20 = 0.5
  - The adjusted subtotal is thus $25*0.5 = $12.5
  - The adjusted price for a single Part 1234 is then $12.5/10 = $1.25
- Calculations for Part 5678:
  - The subtotal for all twenty Parts 5678 is therefore $0.5*20 = $10
  - The portion of the total paid is therefore 10/20 = 0.5
  - The adjusted subtotal is thus $25*0.5 = $12.5
  - The adjusted price for a single Part 5678 is then $12.5/20 = $0.625

The adjusted price and adjusted subtotal of each order line item are
determined by the first of the following rules that applies:
1. If the line item is fully refunded or otherwise has a net quantity of
   zero then it has no adjusted price or adjusted subtotal and these are
   output as blank, but the recorded subtotal and price output as usual.
2. If the order total is less than zero then:
   * The order's items have no adjusted price or adjusted subtotal and
     these are output as blank;
   * The order is not included in aggregations and calculations for the
     summary sheet;
   * A details sheet for the order is still generated.
3. If the order subtotal is greater than zero then the adjusted price
   and subtotal are calculated proportionally as described above.
4. Otherwise, i.e., the order subtotal is zero, the total is zero or
   greater, and the order's net quantity is greater than zero, the
   adjusted price is the total divided by the order's net quantity
   across all line items, and the adjusted subtotal is that adjusted
   price times the line item's net quantity.  A total of zero thus
   yields adjusted prices and subtotals of $0.

If an order's net quantity is zero but its total is greater than zero,
e.g., all items were refunded but not shipping, then by rule 1 that
total is not attributed to any item and does not appear in the summary
sheet's adjusted values.

Median and mean are weighted by net-of-refund quantity.  E.g., the mean
price is the subtotal for a given item (order line item or BOID
aggregate) divided by the quantity of that item, excluding refunds.  The
median of an even quantity is the mean of the two middle values.

A missing or blank BOID is presented as a blank in output, but
considered distinct from any other for aggregation and other purposes,
including other blank BOIDs.


## 2. Configuration & Parameters                          ^configuration

`apps.brickowl.summarize-orders` has the following configuration options
in addition to those in the inherited `apps.brickowl.md`:
* `--out`: The filename of the XLSX spreadsheet to write; the default is
  `data/brickowl/orders.xlsx`.  Any existing file is overwritten.  If
  that location is an existing directory, the run aborts with an error.

## 3. Function                                                 ^function

This app operates over cached orders within the configured order scope.
If no orders are in scope the run fails with an error.

An Excel XLSX spreadsheet workbook is written to the output filename.
Any existing file is overwritten and missing parent directories created.
Existing files are not overwritten and no directories created if the run
aborts with an error.  The final workbook is written atomically, i.e.,
as a temp file that is then renamed.

All monetary values are written in United States dollars (USD) with data
in full precision but the cell presented in default USD format.

All monetary and quantity totals exclude refunded items.  Fully refunded
items are not included in Summary Sheet calculations or aggregations but
are listed in the Details Sheets.

### 3.1 Summary Sheet                                     ^summary-sheet

The first sheet of the output presents an aggregate summary:
* The first row gives the column headers for the subsequent rows.
* Each subsequent row presents data for one item as identified by BOID,
  computed across all orders processed in this run and all conditions
  for the item, sorted by decreasing adjusted subtotal, decreasing
  quantity, name, then
  BOID natural comparison:
  * BOID
  * Natural ID
  * Type
  * Name
  * Color
  * Quantity
  * Minimum Adjusted Price
  * Maximum Adjusted Price
  * Median Adjusted Price
  * Mean Adjusted Price
  * Adjusted Subtotal (sum of adjusted prices paid for this BOID)
  * Minimum Price
  * Maximum Price
  * Median Price
  * Mean Price
  * Subtotal (sum of prices paid for this BOID)
  * Orders (comma separated list of unique contributing order IDs sorted
    by quantity contributed and then order ID)

### 3.2 Details Sheets                                   ^details-sheets

Subsequent sheets of the output present the details for each order,
sorted by the UTC instant placed (most recent first) then order ID:
* These sheets are labeled by the store name---shortened and
  sanitized---and the date the order was placed (in local system time).
  If any shortened & sanitized store names collide in a case-insensitive
  comparison (i.e., same short form is generated for different store
  IDs, ignoring capitalization and not including the order date) then
  the store ID is included in the names of the colliding stores (which
  may entail additional shortening).  If multiple orders were placed to
  a single store ID on the same day (local system time) then all those
  orders (including the first) are given " (X)" suffixes where X
  decreases until the earliest order (thus latest in the workbook) is
  assigned an X of 1.
* The first row of each of these sheets reports a labeled summary:
  * Store Name
  * Store ID
  * Order ID
  * Order Date
  * Order Status
  * BOIDs (number of distinct BOIDs)
  * Quantity (number of items)
  * Total (payment net-of-refund)
* The second row is the column headers for the subsequent rows.
* Each of the subsequent rows reports a line item for the order, in
  order by decreasing adjusted subtotal, decreasing quantity,
  BOID natural comparison, condition, then line item position:
  * BOID
  * Natural ID
  * Type
  * Name
  * Color
  * Condition
  * Quantity
  * Adjusted Price
  * Adjusted Subtotal (sum of adjusted prices paid for this line item)
  * Price
  * Subtotal (sum of prices paid for this line item)

Note that the order details sheet captures each line item in an order,
and BOID+condition pairs might repeat.  The overall summary sheet though
aggregates identical BOIDs regardless of condition.


## 4. Incorrect, Missing, and Inaccessible Data                  ^errors

Any unavailable or invalid data that affects sorting or quantity and
monetary calculations results in an error and aborted run, including:
* Missing or malformed `iso_order_time`;
* Malformed `ordered_quantity` or `refunded_quantity`;
* Missing `base_price_USD`;
* Missing data necessary to compute a total, or an undefined total;
* The `refunded_quantity` is greater than the `ordered_quantity`;
* Negative prices or quantities.
