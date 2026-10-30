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

The Brick Owl API is documented in `docs/APIs/API Documentation - Brick
Owl.html`, a local cache of https://www.brickowl.com/api_docs

No consideration for rate limits and quotas is necessary until proven
otherwise, expected usage fits well within Brick Owl parameters.

Appropriate handling of data for GDPR compliance and other
considerations is left to the user of these tools.


## 2. Common Configuration & Parameters                          ^config

Command line parameters have precedence over any configuration file.

The Brick Owl API Key to use may be either specified on the command line
(`--key`) or read from a configuration file, defaulting to
`.conf/brickowl.jawn` but also specifiable (`--conf`).

Input dates, i.e., from command line parameters, are accepted in either
`YYYYMMDD`, `YYYY-MM-DD`, or `YYYY/MM/DD` format and assume local time.
