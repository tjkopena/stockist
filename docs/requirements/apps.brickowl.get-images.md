# Brick Owl: apps.brickowl.get-images

This document outlines `apps.brickowl.get-images`, a command line
program for downloading item images from the Brick Owl ecommerce site.
It is part of the overall `stockist` collection of tools for working
with several specific niche ecommerce stores and suppliers.

This application inherits background information, features, and
requirements from the `apps.brickowl.md` document.


## 1. Functional Overview                                      ^overview

`apps.brickowl.get-images` works over a cache of Brick Owl orders in
local files, i.e., downloaded using `apps.brickowl.get-orders`.  Item
data in the orders contains a URL for a small image.  If an item image
is not already present in a local folder, it is downloaded.


## 2. Configuration & Parameters                          ^configuration

`apps.brickowl.get-images` has no configuration options beyond those in
the inherited `apps.brickowl.md`.


## 3. Function                                                 ^function


`apps.brickowl.get-images` operates over cached orders within the
configured scope.  If no orders are in scope or scope construction
encounters an error then the run aborts with an error.

If the image cache location (§apps.brickowl.md:image-cache:2.6) exists
and is not a folder, the run aborts with an error.  If the folder does
not exist it is created, including any parent directories.

Every item in every cached order within scope is scanned.  Items with no
BOID or no `image_small` are flagged then skipped; this does not result
in the run ending with an error code.

If the file `<BOID>.75px.png` for a given item and its BOID does not
exist in the image cache then its `image_small` is downloaded, converted
to PNG and 75x75 pixels if necessary, and written to that file.  If
necessary, resizing is done by scaling the downloaded image to fit
inside 75x75 pixels while maintaining aspect ratio and centering the
resized image on a white background.

If the image is newly downloaded or the file `<BOID>.25px.png` does not
exist, the 75x75 image is downsampled to 25x25 pixels and written to
that file.  Note that if the `image_small` is downloaded in this run,
the 25x25 version is generated and written regardless of whether or not
it exists.  If reading the 75x75 image generates an error then it is
re-downloaded and the resizing tried again.  If that fails the error is
flagged and the run continues but ends with an error code.

Any errors downloading, decoding, or writing an image are flagged but
the run continues and then ends with an error code.
