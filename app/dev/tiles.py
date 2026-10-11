"""Caching tile proxy for the console's base map (T50), served by app/dev/live_server.py.

  GET  /api/tiles/<layer>/<z>/<x>/<y>      one 256 px tile: from runs/app/tiles/ when cached, else fetched once
  POST /api/tiles/prefetch                 {run_id, question_id, layer}: the tiles behind one question's options

Layers: streets (OpenStreetMap standard tiles, © OpenStreetMap contributors) and satellite (Esri World Imagery).
Gentle on the tile servers, as the OSM tile usage policy asks: a User-Agent naming the project, a disk cache that
is always used first, at most 2 upstream fetches at a time per layer, no retry of a failed tile for a minute, and
a layer that keeps failing is skipped for 30 s, so a dead network fails fast. Prefetch is sequential, runs only
when the console asks for an open question, and stops at PREFETCH_CAP tiles below zoom 17.
"""
import math
import os
import queue
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

USER_AGENT = ("AquiOperatorConsole/1.0 (JunctionX Lisbon 2026 panorama localisation team; "
              "+https://github.com/PedroMattaMPT)")
LAYERS = {
    "streets": {"name": "Streets", "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png", "ext": "png",
                "max_zoom": 19, "attribution": "© OpenStreetMap contributors",
                "attribution_url": "https://www.openstreetmap.org/copyright"},
    "satellite": {"name": "Satellite", "ext": "jpg", "max_zoom": 19,
                  "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                  "attribution": "Imagery © Esri, Maxar, Earthstar Geographics, and the GIS User Community",
                  "attribution_url": "https://www.esri.com/en-us/legal/terms/full-master-agreement"},
}
MAX_TILE = 2 * 1024 * 1024
PREFETCH_CAP = 48
PREFETCH_MAX_ZOOM = 16


class TileError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def content_type(data):
    return "image/png" if data[:4] == b"\x89PNG" else "image/jpeg" if data[:2] == b"\xff\xd8" else "application/octet-stream"


def tile_xy(lat, lng, z):
    """The XYZ (Web Mercator) tile holding (lat, lng) at zoom z."""
    n = 2 ** z
    lat = max(-85.05112, min(85.05112, lat))
    x = int((lng + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
    return min(max(x, 0), n - 1), min(max(y, 0), n - 1)


def tiles_in(bounds, z):
    south, west, north, east = bounds
    x0, y0 = tile_xy(north, west, z)
    x1, y1 = tile_xy(south, east, z)
    return [(z, x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]


def option_geometry(options):
    """(bounds (south, west, north, east) or None, [(lat, lng, radius_m)]) of a question's options.

    Zones count by their polygon or extent, places by their point and radius. "Outside" / "None of these"
    options cover the rest of the scope, so they add nothing.
    """
    lats, lngs, points = [], [], []

    def add(lat, lng):
        if isinstance(lat, (int, float)) and isinstance(lng, (int, float)) and abs(lat) <= 90 and abs(lng) <= 180:
            lats.append(float(lat))
            lngs.append(float(lng))

    def walk(coords):  # GeoJSON [lng, lat] at any depth (Polygon, MultiPolygon)
        if isinstance(coords, (list, tuple)) and len(coords) >= 2 and all(isinstance(v, (int, float)) for v in coords[:2]):
            add(coords[1], coords[0])
        elif isinstance(coords, (list, tuple)):
            for item in coords:
                walk(item)

    for option in options or []:
        if not isinstance(option, dict) or option.get("complement") or option.get("none"):
            continue
        zone, extent, point = option.get("zone"), option.get("extent"), option.get("point")
        if isinstance(zone, dict) and zone.get("coordinates"):
            walk(zone["coordinates"])
        elif isinstance(extent, dict) and all(k in extent for k in ("south", "west", "north", "east")):
            add(extent["south"], extent["west"])
            add(extent["north"], extent["east"])
        if isinstance(point, (list, tuple)) and len(point) == 2:
            point = {"lat": point[0], "lng": point[1]}
        if isinstance(point, dict) and isinstance(point.get("lat"), (int, float)) and isinstance(point.get("lng"), (int, float)):
            lat, lng = float(point["lat"]), float(point["lng"])
            radius = option.get("radius_m") if isinstance(option.get("radius_m"), (int, float)) else None
            add(lat, lng)
            if radius and not zone and not extent:
                dlat = radius / 111320.0
                dlng = radius / (111320.0 * max(0.2, math.cos(math.radians(lat))))
                add(lat - dlat, lng - dlng)
                add(lat + dlat, lng + dlng)
            points.append((lat, lng, radius))
    if not lats:
        return None, points
    return (min(lats), min(lngs), max(lats), max(lngs)), points


def prefetch_tiles(options, cap=PREFETCH_CAP):
    """The tiles the team is likely to open for one question: the options' extent at its fitting zoom and one
    deeper, then the street-level tiles around each place option (zooms 15-16). At most `cap`, none above 16."""
    bounds, points = option_geometry(options)
    out = []
    if bounds:
        south, west, north, east = bounds
        span = max(east - west, (north - south) * 1.75, 1e-4) * 1.3  # as the console's questionView
        fit = int(max(2, min(PREFETCH_MAX_ZOOM, round(math.log2(720.0 / span)))))
        for z in (fit, min(fit + 1, PREFETCH_MAX_ZOOM)):
            out += tiles_in(bounds, z)
    for lat, lng, radius in points:
        if radius is None or radius > 5000:  # zones (no radius) and wide places: their street tiles are guesses
            continue
        for z in (15, 16):
            n = 2 ** z
            fx, fy = (lng + 180.0) / 360.0 * n, (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
            x, y = int(fx), int(fy)
            nx, ny = x + (1 if fx - x >= 0.5 else -1), y + (1 if fy - y >= 0.5 else -1)
            out += [(z, a % n, b) for a in (x, nx) for b in (y, ny) if 0 <= b < n]
    seen, unique = set(), []
    for tile in out:
        if tile not in seen:
            seen.add(tile)
            unique.append(tile)
    return unique[:cap]


class TileProxy:
    """Disk-cached tiles for the console. get() never raises anything but TileError."""

    def __init__(self, root, layers=None, timeout=6.0, per_layer=2, retry_after=60.0, breaker_failures=4,
                 breaker_s=30.0, log=print):
        self.root = Path(root)
        self.layers = layers or LAYERS
        self.timeout, self.retry_after = timeout, retry_after
        self.breaker_failures, self.breaker_s = breaker_failures, breaker_s
        self.log = log
        self.slots = {name: threading.BoundedSemaphore(per_layer) for name in self.layers}
        self.lock = threading.Lock()
        self.inflight, self.failed = {}, {}
        self.streak = {name: 0 for name in self.layers}
        self.down_until = {name: 0.0 for name in self.layers}
        self.stats = {"cached": 0, "fetched": 0, "failed": 0, "prefetched": 0}
        self.jobs = queue.Queue()
        self.generation = 0
        threading.Thread(target=self._prefetcher, daemon=True, name="tile-prefetch").start()

    def describe(self):
        """The layer list for /api/status: the console builds its map sources from it."""
        return [{"id": name, "name": spec["name"], "url": f"/api/tiles/{name}/{{z}}/{{x}}/{{y}}",
                 "max_zoom": spec["max_zoom"], "attribution": spec["attribution"],
                 "attribution_url": spec.get("attribution_url")} for name, spec in self.layers.items()]

    def path(self, layer, z, x, y):
        return self.root / layer / str(z) / str(x) / f"{y}.{self.layers[layer]['ext']}"

    def check(self, layer, z, x, y):
        if layer not in self.layers:
            raise TileError(404, f"No tile layer {layer!r}.")
        if not (0 <= z <= self.layers[layer]["max_zoom"] and 0 <= x < 2 ** z and 0 <= y < 2 ** z):
            raise TileError(404, "Tile outside the layer's range.")

    def get(self, layer, z, x, y):
        """(data, content type, cached) for one tile; TileError (404, 503 or 504) when unavailable."""
        self.check(layer, z, x, y)
        file = self.path(layer, z, x, y)
        if file.is_file():
            data = file.read_bytes()
            self.stats["cached"] += 1
            return data, content_type(data), True
        key, name = (layer, z, x, y), self.layers[layer]["name"]
        with self.lock:
            now = time.monotonic()
            if self.down_until[layer] > now:
                raise TileError(503, f"{name} tiles are unreachable; retrying in {self.down_until[layer] - now:.0f} s.")
            if now - self.failed.get(key, -1e9) < self.retry_after:
                raise TileError(504, f"This {name.lower()} tile failed recently; not retried yet.")
            event = self.inflight.get(key)
            owner = event is None
            if owner:
                event = self.inflight[key] = threading.Event()
        if not owner:  # another request is fetching this tile: share its result
            event.wait(self.timeout * 2 + 1)
            if file.is_file():
                data = file.read_bytes()
                return data, content_type(data), True
            raise TileError(504, f"{name} tile unavailable.")
        try:
            data = self._fetch(layer, z, x, y)
            file.parent.mkdir(parents=True, exist_ok=True)
            part = file.with_name(f".{file.name}.{os.getpid()}.{threading.get_ident()}.part")
            part.write_bytes(data)
            os.replace(part, file)
            with self.lock:
                self.streak[layer] = 0
                self.failed.pop(key, None)
            self.stats["fetched"] += 1
            return data, content_type(data), False
        except TileError:
            self.stats["failed"] += 1
            raise
        except Exception as exc:  # noqa: BLE001  network, DNS, TLS, HTTP errors: the map shows its overlay anyway
            self.stats["failed"] += 1
            with self.lock:
                self.failed[key] = time.monotonic()
                self.streak[layer] += 1
                if self.streak[layer] >= self.breaker_failures:
                    self.down_until[layer] = time.monotonic() + self.breaker_s
                    self.streak[layer] = 0
                    self.log(f"tiles: {name} unreachable ({type(exc).__name__}: {exc}); pausing {self.breaker_s:.0f} s")
            raise TileError(504, f"{name} tile unavailable: {type(exc).__name__}.") from None
        finally:
            with self.lock:
                self.inflight.pop(key, None)
            event.set()

    def _fetch(self, layer, z, x, y):
        spec = self.layers[layer]
        if not self.slots[layer].acquire(timeout=self.timeout * 2):
            raise TileError(503, f"{spec['name']} tile server busy; try again.")
        try:
            request = urllib.request.Request(spec["url"].format(z=z, x=x, y=y),
                                             headers={"User-Agent": USER_AGENT, "Accept": "image/png,image/jpeg,image/*"})
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = response.read(MAX_TILE + 1)
        finally:
            self.slots[layer].release()
        if not data or len(data) > MAX_TILE or content_type(data) == "application/octet-stream":
            raise ValueError("upstream answer is not a PNG or JPEG tile")
        return data

    def prefetch(self, layer, options):
        """Queue the uncached tiles behind one question's options (replacing any earlier prefetch); returns the count."""
        if layer not in self.layers:
            raise TileError(404, f"No tile layer {layer!r}.")
        tiles = [t for t in prefetch_tiles(options) if t[0] <= self.layers[layer]["max_zoom"]
                 and not self.path(layer, *t).is_file()]
        with self.lock:
            self.generation += 1
            generation = self.generation
        for tile in tiles:
            self.jobs.put((generation, layer, tile))
        return len(tiles)

    def _prefetcher(self):
        while True:
            generation, layer, (z, x, y) = self.jobs.get()
            if generation != self.generation or self.down_until[layer] > time.monotonic():
                continue  # a newer question replaced this one, or the layer is unreachable
            try:
                self.get(layer, z, x, y)
                self.stats["prefetched"] += 1
            except TileError:
                pass
