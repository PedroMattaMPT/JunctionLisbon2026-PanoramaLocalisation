"""Parse a panorama's filename and cut the panorama into perspective views (PLAN.md 3, steps 0-1).

The filename is the only side information a panorama has: EXIF, GPS and XMP are stripped.
`cut_views` uses py360convert to cut 8 overlapping horizontal views plus sky and ground for OCR, the
VLM checklist and the embedding models. `crop` cuts full-resolution crops for OCR rereads. A view
keeps the angles it was cut at, so a pixel or an OCR box in it maps back to the panorama sphere
(`view_xy_to_sphere`, `box_to_sphere`).

Conventions, checked against py360convert 1.0.4 with coloured markers (tests/test_views.py):
- yaw: degrees, relative to the camera. 0 is the centre column of the equirectangular image, and yaw
  increases to the right (clockwise seen from above), wrapped to [0, 360). It equals Pannellum's yaw
  and py360convert's u_deg, both mod 360. The compass heading of yaw 0 is unknown (no metadata).
- pitch: degrees. +90 is straight up, 0 the horizon, -90 straight down; it equals py360convert's v_deg.
- pixels: (x, y) = (column, row). Integers are pixel centres: (0, 0) is the centre of the top-left
  pixel, as in OpenCV and py360convert. The panorama's centre is ((W-1)/2, (H-1)/2). A view's first
  and last pixel centres lie on the edges of its field of view.
- views: square, with the same field of view across and down, and no roll, so the horizon is level
  in the horizontal views h000, h045, ..., h315 (pitch 0, yaw 0, 45, ..., 315). At fov 90, neighbours
  overlap by half. Sky and ground are cut at yaw 0, as if tilting the head up or down from yaw 0:
  yaw 0 is at the bottom of sky and at the top of ground, and yaw 90 is on the right of both.

The photographer zone is the bottom photographer_mask_pct percent of the equirectangular rows,
pitch below -90 + 1.8 * pct degrees (-58.5 at the default 17.5%). The person holding the camera
appears there in almost every panorama. Its pixels are not blanked. Each view carries a mask (True
means the pixel samples the zone) and masked_fraction, so later stages decide whether to skip, flag
or read those pixels (PLAN.md 3.1: track what was masked rather than discarding ground clues). At
fov 90 the horizontal views reach down only to pitch -35.3 in their corners, so only ground is
masked (29.5% of it at 17.5%).

Filenames look like IMG_20250125_142313_00_141.jpg: date, time, a raw field ("00" in every warm-up
file, meaning unknown) and the shot counter. The time is read as UTC. Our own sun-heading checks
point that way, but the organisers have not confirmed it, so PanoramaName records it as an
assumption. The camera seems to use interval mode: two warm-up files share a timestamp but have
different counters. So a timestamp may mark the start of a series, and the shot itself can be
later. Its resolution is 1 s at best.

  pano = load_panorama("Data/Panorama Warm-Up/IMG_20250125_142313_00_141.jpg")
  views = cut_views(pano)                             # h000 ... h315, sky, ground: 1024 x 1024, fov 90
  yaw, pitch = view_xy_to_sphere(views[2], 700, 480)  # views[2] is h090
  box = box_to_sphere(views[2], 650, 470, 760, 495)   # {"yaw", "pitch", "w", "h"} for evidence.added
  sign = crop(pano, box["yaw"], box["pitch"], 10)     # a reread at the panorama's own resolution

CLI: python -m panoloc.views <panorama.jpg> [--out DIR] [--size 1024] writes the views as JPEGs plus
views.json (to runs/views/<panorama stem>/ by default) and prints the timing.
"""
import argparse
import json
import math
import os
import re
import time
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import py360convert
from PIL import Image

SCHEMA = "panoloc.views/1"
DEFAULT_SIZE = 1024
DEFAULT_FOV = 90.0
DEFAULT_MASK_PCT = 17.5  # PLAN.md 3.1: the photographer is in the bottom ~15-20%
MAX_CROP_SIZE = 2048
MIN_CROP_SIZE = 16
JPEG_QUALITY = 92
TIMEZONE_ASSUMED = "UTC"
TIMESTAMP_NOTE = ("Read as UTC, which the organisers have not confirmed. The camera seems to use "
                  "interval mode, so this may be the start of a series and the shot can be later.")
FILENAME_RE = re.compile(r"IMG_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_(\d+)_(\d+)(?:\.[a-z0-9]+)?",
                         re.IGNORECASE)
CONVENTIONS = {
    "yaw": "degrees, camera-relative: 0 = centre column of the panorama, increasing to the right, "
           "in [0, 360); compass heading unknown",
    "pitch": "degrees: +90 up, 0 horizon, -90 down",
    "pixels": "x = column, y = row; integers are pixel centres, (0, 0) is the top-left pixel",
    "sky_ground": "cut at yaw 0: yaw 0 at the bottom of sky and at the top of ground, yaw 90 on the right",
    "mask": "True where a view pixel samples the photographer zone (pitch below pitch_below_deg)",
}
REPO_ROOT = Path(__file__).resolve().parent.parent


# -- filename -------------------------------------------------------------------------------------

@dataclass(frozen=True)
class PanoramaName:
    """What a panorama's filename says. When valid is False, every field but name is None."""
    name: str
    valid: bool
    timestamp: datetime | None = None    # timezone-aware, in UTC as timezone_assumed says
    timezone_assumed: str | None = None  # "UTC": our assumption, not confirmed by the organisers
    counter: int | None = None           # the shot counter NNN
    middle: str | None = None            # the raw field between the time and the counter ("00")

    def to_dict(self):
        doc = {"name": self.name, "valid": self.valid,
               "timestamp": self.timestamp.isoformat() if self.timestamp else None,
               "timezone_assumed": self.timezone_assumed, "counter": self.counter, "middle": self.middle}
        if self.timestamp:
            doc["timestamp_note"] = TIMESTAMP_NOTE
        return doc


def parse_filename(name):
    """Parse IMG_YYYYMMDD_hhmmss_00_NNN.jpg (any directory or extension). Never raises."""
    try:
        text = os.fsdecode(name)
    except TypeError:
        text = str(name)
    base = re.split(r"[\\/]", text)[-1]
    m = FILENAME_RE.fullmatch(base)
    if not m:
        return PanoramaName(base, False)
    try:
        timestamp = datetime(*(int(g) for g in m.groups()[:6]), tzinfo=timezone.utc)
    except ValueError:  # an impossible date or time, such as month 13 or hour 25
        return PanoramaName(base, False)
    return PanoramaName(base, True, timestamp, TIMEZONE_ASSUMED, int(m.group(8)), m.group(7))


# -- views ----------------------------------------------------------------------------------------

@dataclass(eq=False)
class View:
    """A perspective view cut from the panorama, with the angles it was cut at (see the conventions)."""
    name: str          # h000 ... h315, sky, ground; "crop" for a cut_view crop
    yaw_deg: float     # where the view's centre looks
    pitch_deg: float
    fov_deg: float     # across and down: views are square
    image: np.ndarray = field(repr=False)  # H x W x 3 uint8 RGB, nothing blanked
    mask: np.ndarray = field(repr=False)   # H x W bool, True = samples the photographer zone
    masked_fraction: float = 0.0

    def meta(self):
        """Everything but the pixels, for views.json and the run log."""
        h, w = self.image.shape[:2]
        return {"name": self.name, "yaw_deg": self.yaw_deg, "pitch_deg": self.pitch_deg, "fov_deg": self.fov_deg,
                "width": w, "height": h, "masked_fraction": round(self.masked_fraction, 4)}


def load_panorama(path):
    """Read an equirectangular panorama as an H x W x 3 RGB uint8 array."""
    with Image.open(path) as im:
        return np.array(im.convert("RGB"))


def photographer_pitch_deg(photographer_mask_pct=DEFAULT_MASK_PCT):
    """Pitch below which a direction lies in the bottom pct percent of the equirectangular rows."""
    if not 0 <= photographer_mask_pct <= 100:
        raise ValueError(f"photographer_mask_pct must be in [0, 100], got {photographer_mask_pct}")
    return -90 + 1.8 * photographer_mask_pct


def cut_views(pano, size=DEFAULT_SIZE, fov_deg=DEFAULT_FOV, n_horizontal=8, photographer_mask_pct=DEFAULT_MASK_PCT):
    """The standard views: n_horizontal at pitch 0 from yaw 0 (h000, h045, ... for 8), then sky and ground."""
    _check_pano(pano)
    _check_angles(0, fov_deg, size)
    photographer_pitch_deg(photographer_mask_pct)  # checks the percentage before any work
    if n_horizontal < 1:
        raise ValueError(f"n_horizontal must be at least 1, got {n_horizontal}")
    angles = [(f"h{round(i * 360 / n_horizontal) % 360:03d}", i * 360 / n_horizontal, 0.0) for i in range(n_horizontal)]
    angles += [("sky", 0.0, 90.0), ("ground", 0.0, -90.0)]
    masks = {}  # a mask depends on pitch, not yaw: the horizontal views share one computation
    views = []
    for name, yaw, pitch in angles:
        if pitch not in masks:
            masks[pitch] = _photographer_mask(pitch, fov_deg, size, photographer_mask_pct)
        views.append(_view(name, yaw, pitch, fov_deg, crop(pano, yaw, pitch, fov_deg, size), masks[pitch].copy()))
    return views


def cut_view(pano, yaw_deg, pitch_deg, fov_deg=DEFAULT_FOV, size=None, *, name="crop",
             photographer_mask_pct=DEFAULT_MASK_PCT):
    """One square View looking at yaw/pitch, masked like the standard views; size=None picks crop_size.

    For a reread whose OCR boxes must map back to the sphere (view_xy_to_sphere, box_to_sphere).
    """
    image = crop(pano, yaw_deg, pitch_deg, fov_deg, size)
    mask = _photographer_mask(pitch_deg, fov_deg, image.shape[0], photographer_mask_pct)
    return _view(name, yaw_deg, pitch_deg, fov_deg, image, mask)


def _view(name, yaw_deg, pitch_deg, fov_deg, image, mask):
    return View(name, float(_wrap(yaw_deg)), float(pitch_deg), float(fov_deg), image, mask, float(mask.mean()))


def crop_size(fov_deg, pano_width):
    """The side at which a crop's centre keeps the panorama's resolution, capped at MAX_CROP_SIZE.

    The panorama has pano_width / 360 px per degree; for small fields of view the side is close to
    fov_deg * pano_width / 360. A perspective image is denser towards its edges than at its centre,
    so a crop that matches the source at its centre loses no detail anywhere.
    """
    _check_fov(fov_deg)
    side = math.ceil(pano_width * math.tan(math.radians(fov_deg) / 2) / math.pi + 1)
    return max(MIN_CROP_SIZE, min(MAX_CROP_SIZE, side))


def crop(pano, yaw_deg, pitch_deg, fov_deg, size=None):
    """A square perspective crop (H x W x 3 uint8) for rereads; size=None picks crop_size(fov_deg, W)."""
    _check_pano(pano)
    size = crop_size(fov_deg, pano.shape[1]) if size is None else size
    _check_angles(pitch_deg, fov_deg, size)
    u_deg = (yaw_deg + 180) % 360 - 180  # py360convert's u_deg is our yaw in [-180, 180): same sign
    return py360convert.e2p(pano, float(fov_deg), u_deg, float(pitch_deg), (size, size), mode="bilinear")


# -- angles ---------------------------------------------------------------------------------------

def view_xy_to_sphere(view, x, y):
    """Pixel (x, y) of a view -> (yaw_deg, pitch_deg) on the panorama sphere. Takes scalars or arrays.

    At the exact zenith or nadir yaw is undefined; it is then reported as the view's own yaw.
    """
    h, w = view.image.shape[:2]
    right, up, front = _rays(x, y, view.yaw_deg, view.pitch_deg, view.fov_deg, w, h)
    yaw, pitch = _angles(right, up, front, view.yaw_deg)
    return _plain(yaw), _plain(pitch)


def box_to_sphere(view, x0, y0, x1, y1):
    """An axis-aligned box in a view -> {"yaw", "pitch", "w", "h"} in degrees, the event-log box format.

    yaw/pitch is the box centre. w and h are the angles between the midpoints of the box's left and
    right edges and of its top and bottom edges, which stay meaningful in the sky and ground views.
    """
    h, w = view.image.shape[:2]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rays = np.stack(_rays(np.array([cx, x0, x1, cx, cx], float), np.array([cy, cy, cy, y0, y1], float),
                          view.yaw_deg, view.pitch_deg, view.fov_deg, w, h), axis=-1)
    yaw, pitch = _angles(*rays[0], view.yaw_deg)
    return {"yaw": round(float(yaw), 2) % 360, "pitch": round(float(pitch), 2),
            "w": round(_angle_between(rays[1], rays[2]), 2), "h": round(_angle_between(rays[3], rays[4]), 2)}


def sphere_to_pano_xy(yaw_deg, pitch_deg, width, height):
    """(yaw, pitch) -> (x, y) in a width x height equirectangular image: x in [0, width), y in [-0.5, height - 0.5].

    Takes scalars or arrays. Use round(x) % width and clip(round(y), 0, height - 1) for the pixel.
    """
    x = ((np.asarray(yaw_deg, float) / 360 + 0.5) * width - 0.5) % width % width
    y = (0.5 - np.clip(np.asarray(pitch_deg, float), -90, 90) / 180) * height - 0.5
    return _plain(x), _plain(y)


def pano_xy_to_sphere(x, y, width, height):
    """(x, y) in a width x height equirectangular image -> (yaw_deg, pitch_deg); inverse of sphere_to_pano_xy."""
    yaw = _wrap(((np.asarray(x, float) + 0.5) / width - 0.5) * 360)
    pitch = (0.5 - (np.asarray(y, float) + 0.5) / height) * 180
    return _plain(yaw), _plain(pitch)


def _rays(x, y, yaw_deg, pitch_deg, fov_deg, width, height):
    """Direction (right, up, front) of pixel (x, y) in a perspective image; right points to yaw 90, front to yaw 0.

    The same model as py360convert.e2p: a pinhole camera whose first and last pixel centres lie on the
    edges of the field of view, pitched about its own x axis, then turned by yaw about the vertical.
    """
    t = math.tan(math.radians(fov_deg) / 2)
    cam_x = (2 * np.asarray(x, float) / (width - 1) - 1) * t
    cam_y = (1 - 2 * np.asarray(y, float) / (height - 1)) * t
    p, a = math.radians(pitch_deg), math.radians(yaw_deg)
    up = cam_y * math.cos(p) + math.sin(p)
    ahead = math.cos(p) - cam_y * math.sin(p)  # horizontal component along the view's own yaw
    return cam_x * math.cos(a) + ahead * math.sin(a), up, ahead * math.cos(a) - cam_x * math.sin(a)


def _angles(right, up, front, fallback_yaw):
    horizontal = np.hypot(right, front)
    yaw = np.where(horizontal > 1e-12, np.degrees(np.arctan2(right, front)), fallback_yaw)
    return _wrap(yaw), np.degrees(np.arctan2(up, horizontal))


def _angle_between(a, b):
    return math.degrees(math.atan2(np.linalg.norm(np.cross(a, b)), np.dot(a, b)))


def _wrap(yaw):
    return yaw % 360 % 360  # the second % turns the 360.0 that rounding can leave (e.g. -1e-15 % 360) into 0


def _plain(value):
    return float(value) if np.ndim(value) == 0 else value


def _photographer_mask(pitch_deg, fov_deg, size, photographer_mask_pct):
    """View pixels that sample the photographer zone; yaw doesn't change it."""
    limit = photographer_pitch_deg(photographer_mask_pct)
    xs, ys = np.arange(size, dtype=float)[None, :], np.arange(size, dtype=float)[:, None]
    right, up, front = _rays(xs, ys, 0.0, pitch_deg, fov_deg, size, size)
    return np.degrees(np.arctan2(up, np.hypot(right, front))) < limit


def _check_pano(pano):
    if not (isinstance(pano, np.ndarray) and pano.ndim == 3 and pano.shape[2] == 3 and pano.dtype == np.uint8):
        raise ValueError(f"expected an H x W x 3 uint8 RGB panorama, got {getattr(pano, 'shape', None)} "
                         f"{getattr(pano, 'dtype', type(pano).__name__)}")
    h, w = pano.shape[:2]
    if w != 2 * h:
        warnings.warn(f"panorama is {w} x {h}, not 2:1; angles assume a full 360 x 180 degree equirectangular image",
                      stacklevel=3)


def _check_fov(fov_deg):
    if not 0 < fov_deg < 180:
        raise ValueError(f"fov_deg must be in (0, 180), got {fov_deg}")


def _check_angles(pitch_deg, fov_deg, size):
    if not -90 <= pitch_deg <= 90:
        raise ValueError(f"pitch_deg must be in [-90, 90], got {pitch_deg}")
    _check_fov(fov_deg)
    if isinstance(size, bool) or not isinstance(size, (int, np.integer)) or size < 2:
        raise ValueError(f"size must be an integer of at least 2, got {size!r}")


# -- CLI ------------------------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m panoloc.views",
                                     description="Cut a panorama into 8 horizontal views plus sky and ground.")
    parser.add_argument("panorama", type=Path)
    parser.add_argument("--out", type=Path, help="output folder (default: runs/views/<panorama stem>/)")
    parser.add_argument("--size", type=int, default=DEFAULT_SIZE, help=f"view side in pixels (default {DEFAULT_SIZE})")
    parser.add_argument("--fov", type=float, default=DEFAULT_FOV, help=f"field of view in degrees (default {DEFAULT_FOV:g})")
    parser.add_argument("--mask-pct", type=float, default=DEFAULT_MASK_PCT,
                        help=f"photographer zone, bottom percent of the rows (default {DEFAULT_MASK_PCT})")
    parser.add_argument("--overlay", action="store_true",
                        help="also write <view>.mask.jpg with the photographer zone tinted, for masked views")
    args = parser.parse_args(argv)
    out = args.out or REPO_ROOT / "runs" / "views" / args.panorama.stem

    t0 = time.perf_counter()
    pano = load_panorama(args.panorama)
    t1 = time.perf_counter()
    views = cut_views(pano, size=args.size, fov_deg=args.fov, photographer_mask_pct=args.mask_pct)
    t2 = time.perf_counter()
    out.mkdir(parents=True, exist_ok=True)
    entries = []
    for v in views:
        Image.fromarray(v.image).save(out / f"{v.name}.jpg", quality=JPEG_QUALITY)
        if args.overlay and v.masked_fraction > 0:
            tinted = v.image.copy()
            tinted[v.mask] = (0.5 * tinted[v.mask] + [127, 0, 0]).astype(np.uint8)
            Image.fromarray(tinted).save(out / f"{v.name}.mask.jpg", quality=JPEG_QUALITY)
        entries.append({"file": f"{v.name}.jpg", **v.meta()})
    t3 = time.perf_counter()

    timing = {"load_s": round(t1 - t0, 3), "cut_s": round(t2 - t1, 3), "write_s": round(t3 - t2, 3)}
    doc = {"schema": SCHEMA, "panorama": args.panorama.name, "source": str(args.panorama),
           "panorama_size": {"width": pano.shape[1], "height": pano.shape[0]},
           "filename": parse_filename(args.panorama).to_dict(), "conventions": CONVENTIONS,
           "photographer_mask": {"pct": args.mask_pct, "pitch_below_deg": photographer_pitch_deg(args.mask_pct)},
           "views": entries, "timing": timing}
    (out / "views.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"{args.panorama.name}  {pano.shape[1]} x {pano.shape[0]}  ->  {out}")
    for e in entries:
        print(f"  {e['name']:<7} yaw {e['yaw_deg']:6.1f}  pitch {e['pitch_deg']:6.1f}  fov {e['fov_deg']:g}  "
              f"masked {e['masked_fraction']:.3f}")
    print(f"load {timing['load_s']:.2f} s, cut {len(views)} views at {args.size} x {args.size} "
          f"{timing['cut_s']:.2f} s, write {timing['write_s']:.2f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
