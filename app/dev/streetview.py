"""On-demand street imagery for the operator, independent of runs and model inputs.

Only coordinates go upstream. Metadata and public images are cached locally; no upload,
crop, event, cue or penalty is read or written here. Panoramax works without a key.
"""
import hashlib
import ipaddress
import json
import math
import os
import re
import socket
import threading
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

USER_AGENT = "AquiOperatorConsole/1.0 (+https://github.com/PedroMattaMPT; street imagery)"
SAFE_ID = re.compile(r"[a-zA-Z0-9-]{1,80}\Z")
HOSTS = {"api.panoramax.xyz", "panoramax.openstreetmap.fr", "panoramax.ign.fr", "graph.mapillary.com",
         "panoramax-storage-public-fast.s3.gra.perf.cloud.ovh.net"}


def coordinates(lat, lng):
    lat, lng = float(lat), float(lng)
    if not math.isfinite(lat) or not math.isfinite(lng) or abs(lat) > 85 or abs(lng) > 180:
        raise ValueError("A valid latitude and longitude are required.")
    return lat, lng


def distance(a, b):
    lat1, lng1, lat2, lng2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(h)))


def heading(properties):
    for key in ("view:azimuth", "pers:yaw", "computed_compass_angle", "compass_angle"):
        value = properties.get(key)
        if isinstance(value, (int, float)) and math.isfinite(value):
            return value % 360
    return None


def nearby_pictures(pictures):
    """Reserve the closest picture from each image host before filling eight slots.

    The federation catalog can list a working instance beside an offline one.
    Eight consecutive photos from the offline instance must not hide that fallback.
    """
    ranked = sorted((p for p in pictures if p["distance_m"] <= 1000), key=lambda p: p["distance_m"])
    instances = {}
    for photo in ranked:
        instances.setdefault(urllib.parse.urlsplit(photo["sd"]).hostname, photo)
    selected = list(instances.values())[:8]
    seen = {(p["provider"], p["id"]) for p in selected}
    for photo in ranked:
        if len(selected) == 8:
            break
        key = (photo["provider"], photo["id"])
        if key not in seen:
            selected.append(photo)
            seen.add(key)
    return sorted(selected, key=lambda p: p["distance_m"])


def safe_url(value):
    """Only provider-hosted assets from server metadata, never a caller-supplied URL."""
    url = urllib.parse.urlsplit(str(value or ""))
    host = (url.hostname or "").lower()
    if (url.scheme != "https" or url.username or url.password or url.port not in (None, 443)
            or not (host in HOSTS or host.endswith(".fbcdn.net") or host.endswith(".mapillary.com"))):
        raise ValueError("Street image host is not supported.")
    return urllib.parse.urlunsplit(url)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url, limit):
    # IGN redirects its public images to its own object-storage bucket. Validate
    # both hosts and DNS at each hop; never let urllib follow an arbitrary URL.
    for hop in range(2):
        url = safe_url(url)
        host = urllib.parse.urlsplit(url).hostname
        if any(not ipaddress.ip_address(row[4][0]).is_global for row in socket.getaddrinfo(host, 443)):
            raise ValueError("Street image host is not public.")
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=6) as response:
                data = response.read(limit + 1)
            if len(data) > limit:
                raise ValueError("Street image response exceeds the size limit.")
            return data
        except urllib.error.HTTPError as error:
            if hop == 0 and error.code in (301, 302, 303, 307, 308) and error.headers.get('Location'):
                url = urllib.parse.urljoin(url, error.headers['Location'])
                error.close()
            else:
                raise
    raise ValueError("Street image redirected too many times.")


class StreetImagery:
    def __init__(self, root, token=None, fetcher=fetch, clock=time.monotonic):
        self.root, self.token, self.fetcher, self.clock = Path(root), token, fetcher, clock
        self.providers = (["mapillary"] if token else []) + ["panoramax"]
        self.lock = threading.RLock()
        self.slots = {p: threading.BoundedSemaphore(2) for p in self.providers}
        self.failures, self.down_until, self.image_failures = {}, {}, {}

    def _write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_name(f".{path.name}.{threading.get_ident()}.part")
        part.write_bytes(data)
        os.replace(part, path)

    def _request(self, provider, url, limit=4 * 1024 * 1024, image=False):
        url = safe_url(url)
        scope = (provider, urllib.parse.urlsplit(url).hostname)
        with self.lock:
            if self.down_until.get(scope, 0) > self.clock():
                raise ValueError("Street imagery provider is temporarily unavailable.")
        if not self.slots[provider].acquire(timeout=0.1):
            raise ValueError("Street imagery is busy; try again shortly.")
        try:
            data = self.fetcher(url, limit)
            with self.lock:
                self.failures[scope] = 0
            return data
        except Exception:
            with self.lock:
                self.failures[scope] = self.failures.get(scope, 0) + 1
                # A failed image host should not block the federation catalog or
                # another instance. Skip its other images during a short cooldown.
                if self.failures[scope] >= (1 if image else 3):
                    self.down_until[scope] = self.clock() + 30
            raise ValueError("Street imagery provider did not respond.") from None
        finally:
            self.slots[provider].release()

    def _search(self, provider, lat, lng, radius):
        dy = radius / 111320
        dx = dy / max(0.08, math.cos(math.radians(lat)))
        bbox = f"{lng-dx},{lat-dy},{lng+dx},{lat+dy}"
        if provider == "panoramax":
            query = urllib.parse.urlencode({"bbox": bbox, "limit": 100, "filter": "field_of_view=360"})
            data = json.loads(self._request(provider, f"https://api.panoramax.xyz/api/search?{query}"))
            results = []
            for feature in data.get("features", []):
                try:
                    props, assets = feature.get("properties", {}), feature.get("assets", {})
                    lng2, lat2 = feature["geometry"]["coordinates"][:2]
                    lat2, lng2 = coordinates(lat2, lng2)
                    photo_id = str(feature["id"])
                    if not SAFE_ID.fullmatch(photo_id):
                        continue
                    sd = safe_url(assets.get("sd", assets.get("hd", {})).get("href"))
                    hd = safe_url(assets.get("hd", {}).get("href", sd))
                    results.append({"provider": provider, "id": photo_id, "lat": lat2, "lng": lng2,
                                    "distance_m": round(distance((lat, lng), (lat2, lng2)), 1),
                                    "captured_at": props.get("datetime"), "heading_deg": heading(props),
                                    "license": props.get("license", "See source licence"),
                                    "attribution": props.get("geovisio:producer") or "Panoramax contributors",
                                    "page_url": f"https://panoramax.xyz/#pic={photo_id}", "sd": sd, "hd": hd})
                except (KeyError, TypeError, ValueError):
                    continue
            return results
        query = urllib.parse.urlencode({"bbox": bbox, "limit": 50, "is_pano": "true",
                                      "fields": "id,computed_geometry,captured_at,computed_compass_angle,compass_angle,is_pano,thumb_2048_url",
                                      "access_token": self.token})
        data = json.loads(self._request(provider, f"https://graph.mapillary.com/images?{query}"))
        results = []
        for item in data.get("data", []):
            try:
                lng2, lat2 = item["computed_geometry"]["coordinates"][:2]
                lat2, lng2 = coordinates(lat2, lng2)
                photo_id = str(item["id"])
                if not item.get("is_pano") or not SAFE_ID.fullmatch(photo_id):
                    continue
                asset = safe_url(item["thumb_2048_url"])
                results.append({"provider": provider, "id": photo_id, "lat": lat2, "lng": lng2,
                                "distance_m": round(distance((lat, lng), (lat2, lng2)), 1),
                                "captured_at": item.get("captured_at"), "heading_deg": heading(item),
                                "license": "CC BY-SA", "attribution": "Mapillary",
                                "page_url": f"https://www.mapillary.com/app/?pKey={photo_id}", "sd": asset, "hd": asset})
            except (KeyError, TypeError, ValueError):
                continue
        return results

    def nearest(self, lat, lng):
        lat, lng = coordinates(lat, lng)
        key = hashlib.sha256(f"v2,{lat:.6f},{lng:.6f},{','.join(self.providers)}".encode()).hexdigest()
        path = self.root / "search" / f"{key}.json"
        with self.lock:
            if path.is_file():
                cached = json.loads(path.read_text())
                ttl = 86400 if cached["pictures"] else 30
                if time.time() - path.stat().st_mtime < ttl:
                    return cached
            failed = []
            for provider in self.providers:
                try:
                    # Two bounded requests: nearby first, then one wide search. Rank its
                    # results through 150/500/1000 m rather than issuing four requests.
                    pictures = self._search(provider, lat, lng, 50)
                    if not any(p["distance_m"] <= 50 for p in pictures):
                        pictures = self._search(provider, lat, lng, 1000)
                    pictures = nearby_pictures(pictures)
                    if not pictures:
                        continue
                    for photo in pictures:
                        self._write(self.root / provider / photo["id"] / "metadata.json", json.dumps(photo).encode())
                    result = {"pictures": [{k: v for k, v in p.items() if k not in ("sd", "hd")} |
                                           {"image_url": f"/api/streetview/image/{provider}/{p['id']}/sd"} for p in pictures], "unavailable": failed}
                    self._write(path, json.dumps(result).encode())
                    return result
                except (ValueError, OSError, TypeError, json.JSONDecodeError):
                    failed.append(provider)
            result = {"pictures": [], "unavailable": failed}
            self._write(path, json.dumps(result).encode())
            return result

    def image(self, provider, photo_id, size):
        if provider not in self.providers or not SAFE_ID.fullmatch(photo_id) or size not in ("sd", "hd"):
            raise ValueError("Street image not available.")
        path = self.root / provider / photo_id / f"{size}.jpg"
        # Serialise misses so a drag/remount never downloads the same image twice.
        with self.lock:
            if path.is_file():
                return path.read_bytes()
            metadata = path.with_name("metadata.json")
            if not metadata.is_file() or self.image_failures.get((provider, photo_id), 0) > self.clock():
                raise ValueError("Street image not available. Try another nearby picture.")
            try:
                url = json.loads(metadata.read_text())[size]
                data = self._request(provider, url, 25 * 1024 * 1024, image=True)
                if not data.startswith(b"\xff\xd8"):
                    raise ValueError("Street image is not a JPEG.")
                self._write(path, data)
                return data
            except (ValueError, OSError):
                self.image_failures[(provider, photo_id)] = self.clock() + 30
                raise ValueError("Street image unavailable. Try another nearby picture.") from None


class MockStreetImagery:
    providers = ["mock"]

    def __init__(self, image_path):
        self.image_path = image_path

    def nearest(self, lat, lng):
        lat, lng = coordinates(lat, lng)
        return {"pictures": [{"provider": "mock", "id": f"invented-{i}", "lat": lat + (12 + i * 20) / 111320,
                              "lng": lng, "distance_m": 12 + i * 20, "captured_at": None, "heading_deg": 90,
                              "image_url": f"/api/streetview/image/mock/invented-{i}/sd", "page_url": None,
                              "license": "Test fixture", "attribution": "Invented mock image"} for i in range(2)], "unavailable": []}

    def image(self, provider, photo_id, size):
        if provider != "mock" or photo_id not in ("invented-0", "invented-1") or size != "sd":
            raise ValueError("Street image not available.")
        return self.image_path.read_bytes()


def handle(handler, url):
    if not url.path.startswith("/api/streetview/"):
        return False
    if handler.headers.get("Sec-Fetch-Site", "same-origin") not in ("same-origin", "none"):
        handler.json({"error": "Street imagery is for the local console."}, 403)
        return True
    service = getattr(handler.server, "streetview", None)
    if service is None:
        handler.json({"error": "Street imagery is off (--no-streetview)."}, 503)
        return True
    try:
        if url.path == "/api/streetview/nearest":
            params = urllib.parse.parse_qs(url.query)
            handler.json(service.nearest(params.get("lat", [""])[0], params.get("lng", [""])[0]))
            return True
        match = re.fullmatch(r"/api/streetview/image/([a-z]+)/([a-zA-Z0-9-]{1,80})/(sd|hd)", url.path)
        if not match:
            handler.json({"error": "Street image not available."}, 404)
            return True
        data = service.image(*match.groups())
        handler.send_response(200)
        handler.send_header("Content-Type", "image/jpeg")
        handler.send_header("Content-Length", str(len(data)))
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.send_header("Cache-Control", "private, max-age=86400")
        handler.end_headers()
        handler.wfile.write(data)
    except (ValueError, OSError) as error:
        handler.json({"error": str(error)}, 503)
    return True
