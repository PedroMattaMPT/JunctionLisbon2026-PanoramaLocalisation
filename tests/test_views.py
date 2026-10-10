"""Tests for panoloc.views on small synthetic panoramas. Run from the repo root:
.venv/bin/python -m unittest discover -s tests

The synthetic panoramas are built here from the conventions in the module docstring, independently
of panoloc.views: column i is centred on yaw ((i + 0.5) / W - 0.5) * 360 (yaw 0 between the two middle
columns, increasing to the right) and row j on pitch (0.5 - (j + 0.5) / H) * 180 (+90 at the top).
"""
import contextlib
import io
import json
import math
import tempfile
import unittest
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from panoloc.views import (MAX_CROP_SIZE, MIN_CROP_SIZE, View, box_to_sphere, crop, crop_size, cut_view, cut_views,
                           load_panorama, main, pano_xy_to_sphere, parse_filename, photographer_pitch_deg,
                           sphere_to_pano_xy, view_xy_to_sphere)

W, H = 720, 360  # 2 px per degree
HORIZONTAL = [("h000", 0), ("h045", 45), ("h090", 90), ("h135", 135), ("h180", 180), ("h225", 225), ("h270", 270),
              ("h315", 315)]
# No colour is a multiple of another, so a marker blended with the black background never matches one exactly
COLOURS = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255), (255, 128, 0),
           (128, 0, 255), (255, 255, 255), (255, 128, 128)]


def unit(yaw, pitch):
    """Direction as (right, up, front): right towards yaw 90, front towards yaw 0."""
    y, p = math.radians(yaw), math.radians(pitch)
    return np.array([math.cos(p) * math.sin(y), math.sin(p), math.cos(p) * math.cos(y)])


def pixel_directions(w=W, h=H):
    lon = np.radians(((np.arange(w) + 0.5) / w - 0.5) * 360)[None, :]
    lat = np.radians((0.5 - (np.arange(h) + 0.5) / h) * 180)[:, None]
    return np.stack(np.broadcast_arrays(np.cos(lat) * np.sin(lon), np.sin(lat), np.cos(lat) * np.cos(lon)), axis=-1)


def panorama(markers, radius_deg=3.0, w=W, h=H):
    """A black equirectangular image with a disc of colour around each (yaw, pitch, colour)."""
    dirs = pixel_directions(w, h)
    image = np.zeros((h, w, 3), np.uint8)
    for yaw, pitch, colour in markers:
        image[dirs @ unit(yaw, pitch) > math.cos(math.radians(radius_deg))] = colour
    return image


def centroid(image, colour):
    """Mean (x, y) of the pixels of exactly this colour: a marker's interior, without blended edges."""
    ys, xs = np.nonzero(np.all(image == colour, axis=-1))
    if len(xs) < 5:
        raise AssertionError(f"marker {colour} not found ({len(xs)} pixels)")
    return xs.mean(), ys.mean()


def project(yaw, pitch, view_yaw, view_pitch, fov_deg, size):
    """Pinhole projection of a direction into a view, the other way round from panoloc.views."""
    right, up, front = unit(yaw - view_yaw, pitch)  # turn so the view's yaw is straight ahead
    p = math.radians(view_pitch)
    x, y, z = right, up * math.cos(p) - front * math.sin(p), up * math.sin(p) + front * math.cos(p)
    t = math.tan(math.radians(fov_deg) / 2)
    return (x / z / t + 1) / 2 * (size - 1), (1 - y / z / t) / 2 * (size - 1)


def yaw_gap(a, b):
    return abs((a - b + 180) % 360 - 180)


class FilenameTest(unittest.TestCase):
    def test_a_warm_up_name(self):
        name = parse_filename("Data/Panorama Warm-Up/IMG_20250125_142313_00_141.jpg")
        self.assertTrue(name.valid)
        self.assertEqual(name.name, "IMG_20250125_142313_00_141.jpg")
        self.assertEqual(name.timestamp, datetime(2025, 1, 25, 14, 23, 13, tzinfo=timezone.utc))
        self.assertEqual(name.timestamp.utcoffset().total_seconds(), 0)
        self.assertEqual((name.timezone_assumed, name.counter, name.middle), ("UTC", 141, "00"))
        doc = name.to_dict()
        self.assertEqual(doc["timestamp"], "2025-01-25T14:23:13+00:00")
        self.assertIn("interval mode", doc["timestamp_note"])
        json.dumps(doc)

    def test_odd_counters_and_spellings(self):
        cases = {"IMG_20241213_120841_00_059.jpg": 59, "IMG_20241213_120841_00_000.jpg": 0,
                 "IMG_20241213_120841_00_1234.jpg": 1234, "IMG_20241213_120841_00_7.JPG": 7,
                 "IMG_20241213_120841_00_059.jpeg": 59, "IMG_20241213_120841_00_059": 59,
                 "img_20241213_120841_00_059.jpg": 59, r"C:\pano\IMG_20241213_120841_00_059.jpg": 59,
                 Path("x/IMG_20241213_120841_00_059.jpg"): 59}
        for name, counter in cases.items():
            with self.subTest(name=name):
                parsed = parse_filename(name)
                self.assertTrue(parsed.valid)
                self.assertEqual(parsed.counter, counter)
                self.assertEqual(parsed.timestamp, datetime(2024, 12, 13, 12, 8, 41, tzinfo=timezone.utc))
        self.assertEqual(parse_filename("IMG_20260510_121401_07_179.jpg").middle, "07")

    def test_invalid_names_do_not_raise(self):
        for name in ("", "photo.jpg", "IMG_20251325_142313_00_141.jpg", "IMG_20250230_142313_00_141.jpg",
                     "IMG_20250125_256313_00_141.jpg", "IMG_20250125_142360_00_141.jpg", "IMG_2025012_142313_00_141.jpg",
                     "IMG_20250125_142313_00_.jpg", "IMG_20250125_142313_00_141 (1).jpg", "PANO_20250125_142313_00_141.jpg",
                     None, 42, b"IMG_bad.jpg"):
            with self.subTest(name=name):
                parsed = parse_filename(name)
                self.assertFalse(parsed.valid)
                self.assertEqual((parsed.timestamp, parsed.timezone_assumed, parsed.counter, parsed.middle),
                                 (None, None, None, None))
                self.assertNotIn("timestamp_note", parsed.to_dict())


class ViewsTest(unittest.TestCase):
    def test_names_angles_and_shapes(self):
        views = cut_views(panorama([]), size=64)
        self.assertEqual([v.name for v in views], [n for n, _ in HORIZONTAL] + ["sky", "ground"])
        self.assertEqual([v.yaw_deg for v in views], [float(y) for _, y in HORIZONTAL] + [0.0, 0.0])
        self.assertEqual([v.pitch_deg for v in views], [0.0] * 8 + [90.0, -90.0])
        for v in views:
            self.assertIsInstance(v, View)
            self.assertEqual((v.fov_deg, v.image.shape, v.image.dtype), (90.0, (64, 64, 3), np.uint8))
            self.assertEqual((v.mask.shape, v.mask.dtype), ((64, 64), np.bool_))
        self.assertEqual([v.name for v in cut_views(panorama([]), size=16, n_horizontal=4)],
                         ["h000", "h090", "h180", "h270", "sky", "ground"])

    def test_each_marker_appears_at_the_centre_of_its_view(self):
        markers = [(yaw, 0, COLOURS[i]) for i, (_, yaw) in enumerate(HORIZONTAL)]
        markers += [(0, 90, COLOURS[8]), (0, -90, COLOURS[9])]
        size = 201
        views = cut_views(panorama(markers), size=size)
        for view, (_, _, colour) in zip(views, markers):
            with self.subTest(view=view.name):
                x, y = centroid(view.image, colour)
                self.assertAlmostEqual(x, (size - 1) / 2, delta=0.5)
                self.assertAlmostEqual(y, (size - 1) / 2, delta=0.5)

    def test_views_are_upright_not_mirrored_and_sky_and_ground_face_yaw_0(self):
        # (marker yaw, pitch, view): right/left, up/down, wrap-around and the pole views
        cases = [(20, 10, "h000"), (110, -15, "h090"), (250, 5, "h270"), (340, 0, "h315"), (0, 60, "sky"),
                 (90, 60, "sky"), (180, 60, "sky"), (0, -60, "ground"), (90, -60, "ground"), (270, -60, "ground")]
        size = 201
        views = {v.name: v for v in cut_views(panorama([(y, p, COLOURS[i]) for i, (y, p, _) in enumerate(cases)]),
                                              size=size)}
        found = {}
        for i, (yaw, pitch, name) in enumerate(cases):
            with self.subTest(marker=(yaw, pitch), view=name):
                view = views[name]
                x, y = found[i] = centroid(view.image, COLOURS[i])
                ex, ey = project(yaw, pitch, view.yaw_deg, view.pitch_deg, view.fov_deg, size)
                self.assertAlmostEqual(x, ex, delta=1.0)
                self.assertAlmostEqual(y, ey, delta=1.0)
                back_yaw, back_pitch = view_xy_to_sphere(view, x, y)
                self.assertLess(yaw_gap(back_yaw, yaw), 0.5)
                self.assertAlmostEqual(back_pitch, pitch, delta=0.5)
        c = (size - 1) / 2
        self.assertTrue(found[0][0] > c + 20 and found[0][1] < c - 10)  # yaw +20, pitch +10: right of and above centre
        self.assertLess(found[2][0], c - 20)  # yaw 250 is left of h270's centre
        self.assertGreater(found[4][1], c + 20)  # sky: yaw 0 at the bottom
        self.assertGreater(found[5][0], c + 20)  # sky: yaw 90 on the right
        self.assertLess(found[6][1], c - 20)  # sky: yaw 180 at the top
        self.assertLess(found[7][1], c - 20)  # ground: yaw 0 at the top
        self.assertGreater(found[8][0], c + 20)  # ground: yaw 90 on the right
        self.assertLess(found[9][0], c - 20)  # ground: yaw 270 on the left

    def test_every_view_pixel_samples_where_view_xy_to_sphere_says(self):
        # Colour encodes position: red and blue are the sine and cosine of the column angle, green the row
        angle = (np.arange(W) + 0.5) / W * 2 * np.pi
        pano = np.zeros((H, W, 3), np.uint8)
        pano[..., 0] = np.round(127.5 + 127 * np.sin(angle))[None, :]
        pano[..., 2] = np.round(127.5 + 127 * np.cos(angle))[None, :]
        pano[..., 1] = np.round(np.arange(H) / (H - 1) * 255)[:, None]
        grid = np.array([0, 12, 24, 36, 48, 60, 72, 84, 95])
        xs, ys = np.meshgrid(grid, grid)
        for view in cut_views(pano, size=96):
            with self.subTest(view=view.name):
                yaw, pitch = view_xy_to_sphere(view, xs, ys)
                px, py = sphere_to_pano_xy(yaw, pitch, W, H)
                rgb = view.image[ys, xs].astype(float)
                seen_x = (np.arctan2(rgb[..., 0] - 127.5, rgb[..., 2] - 127.5) % (2 * np.pi)) / (2 * np.pi) * W - 0.5
                seen_y = rgb[..., 1] / 255 * (H - 1)
                usable = np.abs(pitch) < 75  # columns converge near the poles
                self.assertGreater(usable.sum(), 20)
                self.assertLess(np.max(np.abs((seen_x - px + W / 2) % W - W / 2)[usable]), 2.0)  # 8-bit coding
                self.assertLess(np.max(np.abs(seen_y - py)), 2.0)

    def test_the_centre_pixel_maps_to_the_views_own_angles(self):
        for size in (64, 65):
            for view in cut_views(panorama([]), size=size):
                with self.subTest(view=view.name, size=size):
                    c = (size - 1) / 2
                    yaw, pitch = view_xy_to_sphere(view, c, c)
                    self.assertIsInstance(yaw, float)
                    self.assertLess(yaw_gap(yaw, view.yaw_deg), 1e-9)
                    self.assertAlmostEqual(pitch, view.pitch_deg, places=9)
                    yaw, pitch = view_xy_to_sphere(view, size // 2, size // 2)  # half a pixel off at most
                    self.assertAlmostEqual(pitch, view.pitch_deg, delta=1.5)
                    if view.name.startswith("h"):
                        self.assertLess(yaw_gap(yaw, view.yaw_deg), 1.5)
        corner_yaw, corner_pitch = view_xy_to_sphere(cut_views(panorama([]), size=64)[0], 63, 63)
        self.assertAlmostEqual(corner_yaw, 45.0, places=6)
        self.assertAlmostEqual(corner_pitch, -math.degrees(math.atan(1 / math.sqrt(2))), places=6)


class SphereTest(unittest.TestCase):
    def test_known_points(self):
        cases = {(0, 0): (359.5, 179.5), (90, 0): (539.5, 179.5), (270, 0): (179.5, 179.5), (-90, 0): (179.5, 179.5),
                 (180, 0): (719.5, 179.5), (360, 45): (359.5, 89.5), (0, 90): (359.5, -0.5), (0, -90): (359.5, 359.5)}
        for (yaw, pitch), expected in cases.items():
            with self.subTest(yaw=yaw, pitch=pitch):
                x, y = sphere_to_pano_xy(yaw, pitch, W, H)
                self.assertIsInstance(x, float)
                self.assertAlmostEqual(x, expected[0], places=9)
                self.assertAlmostEqual(y, expected[1], places=9)
        self.assertEqual(pano_xy_to_sphere(359.5, 179.5, W, H), (0.0, 0.0))
        self.assertEqual(pano_xy_to_sphere(-0.5, -0.5, W, H), (180.0, 90.0))

    def test_round_trips(self):
        rng = np.random.default_rng(0)
        yaw, pitch = rng.uniform(-720, 720, 1000), rng.uniform(-90, 90, 1000)
        x, y = sphere_to_pano_xy(yaw, pitch, 6080, 3040)
        self.assertTrue(np.all((x >= 0) & (x < 6080)))
        back_yaw, back_pitch = pano_xy_to_sphere(x, y, 6080, 3040)
        self.assertTrue(np.all((back_yaw >= 0) & (back_yaw < 360)))
        self.assertLess(np.max(np.abs((back_yaw - yaw + 180) % 360 - 180)), 1e-9)
        self.assertLess(np.max(np.abs(back_pitch - pitch)), 1e-9)
        x, y = rng.uniform(-0.5, 6079.5, 1000), rng.uniform(-0.5, 3039.5, 1000)
        x2, y2 = sphere_to_pano_xy(*pano_xy_to_sphere(x, y, 6080, 3040), 6080, 3040)
        self.assertLess(np.max(np.abs((x2 - x + 3040) % 6080 - 3040)), 1e-6)
        self.assertLess(np.max(np.abs(y2 - y)), 1e-6)
        seam = sphere_to_pano_xy(-179.75 + np.linspace(-1e-12, 1e-12, 2001), 0, W, H)[0]  # x = 0 is at yaw -179.75
        self.assertTrue(np.all((seam >= 0) & (seam < W)))  # rounding never gives x == width
        self.assertLess(pano_xy_to_sphere(np.nextafter(359.5, 0), 179.5, W, H)[0], 360)  # nor yaw == 360

    def test_box_to_sphere(self):
        views = {v.name: v for v in cut_views(panorama([]), size=101)}
        self.assertEqual(box_to_sphere(views["h090"], 0, 0, 100, 100), {"yaw": 90.0, "pitch": 0.0, "w": 90.0, "h": 90.0})
        self.assertEqual(box_to_sphere(views["ground"], 0, 0, 100, 100), {"yaw": 0.0, "pitch": -90.0, "w": 90.0, "h": 90.0})
        box = box_to_sphere(views["h315"], 55, 40, 85, 46)
        yaw, pitch = view_xy_to_sphere(views["h315"], 70, 43)
        self.assertAlmostEqual(box["yaw"], round(yaw, 2))
        self.assertAlmostEqual(box["pitch"], round(pitch, 2))
        self.assertTrue(box["w"] > 3 * box["h"] > 0)


class MaskTest(unittest.TestCase):
    def test_only_the_ground_view_reaches_the_photographer_at_fov_90(self):
        views = {v.name: v for v in cut_views(panorama([]), size=128)}
        for name, _ in HORIZONTAL + [("sky", 0)]:
            self.assertEqual(views[name].masked_fraction, 0.0)
            self.assertFalse(views[name].mask.any())
        disc = math.pi * math.tan(math.radians(90 - 58.5)) ** 2 / 4  # nadir disc of radius 31.5 degrees in a 90-degree view
        self.assertAlmostEqual(views["ground"].masked_fraction, disc, delta=0.01)
        self.assertEqual(views["ground"].masked_fraction, views["ground"].mask.mean())
        self.assertAlmostEqual(photographer_pitch_deg(17.5), -58.5)

    def test_the_mask_marks_the_pixels_that_sample_the_zone_without_blanking_them(self):
        pano = np.zeros((H, W, 3), np.uint8)
        pano[:, :] = (0, 200, 0)
        pano[H - round(H * 0.175):] = (200, 0, 0)  # the bottom 17.5% of the rows (63 of 360)
        ground = cut_views(pano, size=128)[-1]
        red = ground.image[..., 0] > ground.image[..., 1]
        self.assertLess(np.mean(red != ground.mask), 0.01)  # disagreement only on the blended boundary
        self.assertGreater(ground.image[ground.mask][:, 0].min(), 90)  # masked pixels keep the zone's red
        self.assertEqual(tuple(ground.image[64, 64]), (200, 0, 0))

    def test_other_percentages_and_wider_views(self):
        pano = panorama([])
        self.assertEqual(cut_views(pano, size=32, photographer_mask_pct=0)[-1].masked_fraction, 0.0)
        self.assertGreater(cut_views(pano, size=32, photographer_mask_pct=30)[-1].masked_fraction,
                           cut_views(pano, size=32)[-1].masked_fraction)
        wide = cut_views(pano, size=64, fov_deg=120)  # reaches pitch -60 at the bottom of horizontal views
        self.assertTrue(all(v.masked_fraction > 0 for v in wide[:8]))
        self.assertTrue(np.array_equal(wide[0].mask, wide[3].mask))
        self.assertIsNot(wide[0].mask, wide[3].mask)
        view = cut_view(pano, 10, -80, 30, 48)
        self.assertEqual((view.name, view.image.shape, view.masked_fraction), ("crop", (48, 48, 3), 1.0))


class CropTest(unittest.TestCase):
    def test_crop_size_matches_the_panorama_resolution(self):
        self.assertAlmostEqual(crop_size(10, 6080) / (10 * 6080 / 360), 1, delta=0.03)
        self.assertEqual(crop_size(90, 6080), math.ceil(6080 / math.pi + 1))
        self.assertEqual(crop_size(150, 6080), MAX_CROP_SIZE)
        self.assertEqual(crop_size(0.1, 6080), MIN_CROP_SIZE)
        pano = panorama([])
        self.assertEqual(crop(pano, 30, -10, 20).shape, (crop_size(20, W), crop_size(20, W), 3))
        self.assertEqual(crop(pano, 30, -10, 40, size=48).shape, (48, 48, 3))
        view = cut_view(pano, 200, 15, 20)  # same automatic size as crop()
        c = (view.image.shape[0] - 1) / 2
        a, b = unit(*view_xy_to_sphere(view, c, c)), unit(*view_xy_to_sphere(view, c + 1, c))
        step = math.degrees(math.acos(min(1.0, float(a @ b))))
        self.assertTrue(0.9 * 360 / W < step <= 360 / W)  # at least the panorama's own 2 px per degree

    def test_crop_matches_the_view_at_the_same_angles(self):
        pano = panorama([(45, 0, COLOURS[0]), (300, 30, COLOURS[1])])
        self.assertTrue(np.array_equal(crop(pano, 45, 0, 90, 64), cut_views(pano, size=64)[1].image))
        x, y = centroid(crop(pano, -60, 30, 30, 101), COLOURS[1])  # yaw -60 is yaw 300
        self.assertAlmostEqual(x, 50, delta=0.5)
        self.assertAlmostEqual(y, 50, delta=0.5)

    def test_bad_arguments(self):
        pano = panorama([])
        for kwargs in ({"pitch_deg": 91}, {"fov_deg": 180}, {"fov_deg": 0}, {"size": 1}, {"size": 64.0}, {"size": True}):
            args = {"yaw_deg": 0, "pitch_deg": 0, "fov_deg": 60, "size": 32, **kwargs}
            with self.subTest(**kwargs), self.assertRaises(ValueError):
                crop(pano, **args)
        for bad in (pano[..., 0], pano.astype(np.float32), pano[..., :2]):
            with self.assertRaises(ValueError):
                cut_views(bad, size=16)
        for kwargs in ({"photographer_mask_pct": 101}, {"n_horizontal": 0}, {"fov_deg": 200}):
            with self.subTest(**kwargs), self.assertRaises(ValueError):
                cut_views(pano, size=16, **kwargs)
        with self.assertWarns(UserWarning):
            cut_views(np.zeros((360, 700, 3), np.uint8), size=16)


class FilesTest(unittest.TestCase):
    def test_load_panorama_gives_rgb_uint8(self):
        with tempfile.TemporaryDirectory() as tmp:
            for mode in ("L", "RGBA", "RGB"):
                path = Path(tmp) / f"pano_{mode}.png"
                Image.new(mode, (40, 20)).save(path)
                image = load_panorama(path)
                self.assertEqual((image.shape, image.dtype), ((20, 40, 3), np.uint8))
                image[0, 0] = 1  # writable

    def test_cli_writes_views_and_views_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "IMG_20250125_142313_00_141.jpg"
            Image.fromarray(panorama([(0, 0, COLOURS[0])])).save(src, quality=90)
            out = Path(tmp) / "out"
            with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()) as printed:
                warnings.simplefilter("error")
                self.assertEqual(main([str(src), "--out", str(out), "--size", "32"]), 0)
            doc = json.loads((out / "views.json").read_text(encoding="utf-8"))
            self.assertEqual([v["name"] for v in doc["views"]], [n for n, _ in HORIZONTAL] + ["sky", "ground"])
            self.assertEqual(doc["filename"]["counter"], 141)
            self.assertEqual(doc["photographer_mask"], {"pct": 17.5, "pitch_below_deg": -58.5})
            self.assertGreater(doc["views"][-1]["masked_fraction"], 0.25)
            for v in doc["views"]:
                with Image.open(out / v["file"]) as written:
                    self.assertEqual(written.size, (32, 32))
            self.assertIn("cut 10 views", printed.getvalue())


if __name__ == "__main__":
    unittest.main()
