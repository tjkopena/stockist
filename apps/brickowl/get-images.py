if __name__ != '__main__':
    raise Error("This is a script, not intended to be imported")

from io import BytesIO
from os import path
import argparse
import os
import signal
import sys
import tempfile

from PIL import Image
import requests

from apps.brickowl import common
from stockist import brickowl

import logberry


TEMP_PREFIX = '.get-images-'
TEMP_SUFFIX = '.tmp'

TIMEOUT = 30

# Cached image sizes, square, in pixels.
FULL = 75
THUMB = 25

# Image modes the PNG writer accepts as is; others are converted to RGBA.
PNG_MODES = {'1', 'L', 'LA', 'I', 'I;16', 'P', 'RGB', 'RGBA'}


parser = argparse.ArgumentParser(prog='python -m apps.brickowl.get-images',
                                 description='Download item images for cached Brick Owl orders')
common.add_config_arguments(parser)
common.add_scope_arguments(parser)
common.add_images_argument(parser)
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
    settings = common.load_settings(args, options=('images',))
except Exception as e:
    abort("Could not load configuration", error=str(e))

images = args.images or common.DEFAULT_IMAGES
if path.exists(images) and not path.isdir(images):
    abort("Image cache exists and is not a folder", images=images)


#-- Orders ----------------------------------------------------------------

try:
    orders = common.scoped_orders(args, settings.cache)
except common.ScopeError as e:
    abort(str(e))

if not orders:
    abort("No orders in scope")

try:
    os.makedirs(images, exist_ok=True)
except Exception as e:
    abort("Could not create image cache folder", images=images, error=str(e))


#-- Download --------------------------------------------------------------

def _text(item, field):
    v = item.get(field)
    if common.empty(v) or isinstance(v, bool) or not isinstance(v, (str, int)):
        return None
    return str(v).strip()

def fetch(url):
    res = requests.get(url, headers={'User-Agent': brickowl.USER_AGENT}, timeout=TIMEOUT)
    res.raise_for_status()
    return res.content

def image_path(boid, size):
    return common.image_path(images, boid, size)

def save_png(im, fn):
    """Save an image as PNG to fn, atomically."""
    if im.mode not in PNG_MODES:
        im = im.convert('RGBA')
    fd, tmp = tempfile.mkstemp(dir=images, prefix=TEMP_PREFIX, suffix=TEMP_SUFFIX)
    os.close(fd)
    try:
        im.save(tmp, 'PNG')
        os.replace(tmp, fn)
    finally:
        if path.exists(tmp):
            os.remove(tmp)

def normalize(content):
    """Decode an image as FULLxFULL, scaled to fit and centered on white
    if not already that size."""
    with Image.open(BytesIO(content)) as im:
        im.load()
        if im.size == (FULL, FULL):
            return im.copy()
        im = im.convert('RGBA')
    scale = FULL / max(im.size)
    w, h = (max(1, round(d * scale)) for d in im.size)
    im = im.resize((w, h), Image.LANCZOS)
    out = Image.new('RGB', (FULL, FULL), 'white')
    out.paste(im, ((FULL - w) // 2, (FULL - h) // 2), im)
    return out

def downsample(im):
    if im.mode not in ('L', 'LA', 'RGB', 'RGBA'):
        im = im.convert('RGBA')
    return im.resize((THUMB, THUMB), Image.LANCZOS)

def read_full(fn):
    """A cached FULLxFULL image; error if unreadable or the wrong size."""
    with Image.open(fn) as im:
        im.load()
        if im.size != (FULL, FULL):
            raise ValueError(f"Image is {im.size[0]}x{im.size[1]}, not {FULL}x{FULL}")
        return im.copy()

def download(url, boid):
    im = normalize(fetch(url))
    save_png(im, image_path(boid, FULL))
    save_png(downsample(im), image_path(boid, THUMB))

t = logberry.task("Download images", orders=len(orders), images=images)
written = 0
derived = 0
cached = 0
# BOIDs present or written this run, and image URLs that failed.
done = set()
failed = set()
# Items skipped for missing BOID or image (not an error), items skipped
# for bad data, and BOIDs not written.
skipped = 0
flagged = 0
unwritten = []

try:
    for oid, fn, data in orders:
        items = data.get('items')
        if not isinstance(items, list):
            t.warning("Order has no item list, skipped", order_id=oid, file=fn)
            flagged += 1
            continue

        for position, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                t.warning("Item is not a map, skipped", order_id=oid, item=position)
                flagged += 1
                continue

            boid = _text(item, 'boid')
            url = _text(item, 'image_small')
            if boid is None or url is None:
                t.warning("Item has no BOID or no image_small, skipped", order_id=oid, item=position,
                          boid=boid, image_small=url)
                skipped += 1
                continue
            if not common.BOID_FILENAME.fullmatch(boid):
                t.warning("Item BOID not usable as a filename, skipped", order_id=oid, item=position, boid=boid)
                flagged += 1
                continue

            if boid in done or url in failed:
                continue
            if path.isfile(image_path(boid, FULL)):
                if path.isfile(image_path(boid, THUMB)):
                    done.add(boid)
                    cached += 1
                    continue
                try:
                    im = read_full(image_path(boid, FULL))
                except Exception as e:
                    t.warning("Could not read cached image, downloading again", order_id=oid, boid=boid,
                              error=str(e))
                else:
                    try:
                        save_png(downsample(im), image_path(boid, THUMB))
                    except Exception as e:
                        t.warning("Could not write downsampled image", order_id=oid, boid=boid, error=str(e))
                        unwritten.append(boid)
                        continue
                    t.info("Downsampled cached image", boid=boid)
                    done.add(boid)
                    derived += 1
                    continue

            try:
                download(url, boid)
            except Exception as e:
                t.warning("Could not download image", order_id=oid, boid=boid, image_small=url, error=str(e))
                failed.add(url)
                unwritten.append(boid)
                continue
            t.info("Downloaded image", boid=boid)
            done.add(boid)
            written += 1

except BaseException as e:
    t.end_failure("Run terminated", written=written, derived=derived, cached=cached, skipped=skipped,
                  error=str(e) or type(e).__name__)
    logberry.stop()
    if isinstance(e, KeyboardInterrupt):
        sys.exit(130)
    raise

# A BOID that failed under one URL may have been written from another.
unwritten = [b for b in dict.fromkeys(unwritten) if b not in done]
if flagged or unwritten:
    t.end_failure("Some images not downloaded", written=written, derived=derived, cached=cached,
                  skipped=skipped, flagged=flagged, failed=len(unwritten), boids=','.join(unwritten))
else:
    t.end_success(written=written, derived=derived, cached=cached, skipped=skipped)

logberry.stop()
