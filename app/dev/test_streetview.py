"""Display-only street imagery: bounded searches, caches, safe assets and offline routes."""
import json
import io
import socket
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from urllib.error import HTTPError
from unittest.mock import Mock, patch

import streetview as sv


def feature(photo_id="one", lat=48.8576, lng=2.3494, **properties):
    return {"id": photo_id, "geometry": {"coordinates": [lng, lat]},
            "properties": {"datetime": "2025-07-08", "license": "CC-BY-SA-4.0", **properties},
            "assets": {"sd": {"href": f"https://panoramax.openstreetmap.fr/{photo_id}.jpg"}}}


class StreetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aqui-streetview-")
        self.calls = []
        self.now = 10

    def tearDown(self):
        self.temp.cleanup()

    def service(self, features=None, token=None):
        def fetch(url, limit):
            self.calls.append(url)
            return b"\xff\xd8invented" if url.endswith('.jpg') else json.dumps({"features": features or []}).encode()
        return sv.StreetImagery(self.temp.name, token=token, fetcher=fetch, clock=lambda: self.now)

    def test_heading_precedence_and_unknown(self):
        self.assertEqual(sv.heading({"view:azimuth": 209, "pers:yaw": 0}), 209)
        self.assertEqual(sv.heading({"pers:yaw": 365}), 5)
        self.assertIsNone(sv.heading({}))

    def test_nearest_sorted_cached_and_image_only_downloaded_once(self):
        service = self.service([feature("far", lat=48.8580), feature("near")])
        result = service.nearest(48.8576, 2.3494)
        self.assertEqual([p["id"] for p in result["pictures"]], ["near", "far"])
        self.assertNotIn("sd", result["pictures"][0])
        self.assertEqual(service.nearest(48.8576, 2.3494), result)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(service.image("panoramax", "near", "sd"), b"\xff\xd8invented")
        service.image("panoramax", "near", "sd")
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(len(sv.StreetImagery(self.temp.name, fetcher=lambda *a: self.fail("cache miss")).nearest(48.8576, 2.3494)["pictures"]), 2)

    def test_empty_nearby_search_widens_once_and_excludes_beyond_one_km(self):
        calls = []
        def fetch(url, limit):
            calls.append(url)
            return json.dumps({"features": [] if len(calls) == 1 else [feature("near", lat=48.86), feature("too-far", lat=49)]}).encode()
        service = sv.StreetImagery(self.temp.name, fetcher=fetch)
        result = service.nearest(48.8576, 2.3494)
        self.assertEqual([p["id"] for p in result["pictures"]], ["near"])
        widths = [float(parse_qs(urlsplit(url).query)["bbox"][0].split(',')[2]) - float(parse_qs(urlsplit(url).query)["bbox"][0].split(',')[0]) for url in calls]
        self.assertEqual(len(calls), 2)
        self.assertGreater(widths[1], widths[0] * 15)

    def test_missing_token_and_fallback_order(self):
        self.assertEqual(self.service().providers, ["panoramax"])
        def fetch(url, limit):
            self.calls.append(url)
            if 'mapillary' in url:
                raise OSError('offline')
            return json.dumps({"features": [feature()]}).encode()
        service = sv.StreetImagery(self.temp.name, token="test-token", fetcher=fetch)
        result = service.nearest(48.8576, 2.3494)
        self.assertEqual(result["pictures"][0]["provider"], "panoramax")
        self.assertEqual(result["unavailable"], ["mapillary"])
        self.assertNotIn("test-token", json.dumps(result))

    def test_breaker_stops_calls_for_thirty_seconds(self):
        def fetch(url, limit):
            self.calls.append(url)
            raise OSError('offline')
        service = sv.StreetImagery(self.temp.name, fetcher=fetch, clock=lambda: self.now)
        for i in range(4):
            self.assertEqual(service.nearest(48 + i * .01, 2)["pictures"], [])
        self.assertEqual(len(self.calls), 3)
        self.now += 31
        service.nearest(49, 2)
        self.assertEqual(len(self.calls), 4)

    def test_offline_image_instance_keeps_other_instance_and_catalog_available(self):
        pictures = [feature(f"offline-{i}", lat=48.8576 + i * .00001) for i in range(9)]
        fallback = feature("available", lat=48.8579)
        fallback["assets"]["sd"]["href"] = 'https://panoramax.ign.fr/available.jpg'
        pictures.append(fallback)
        offline = True
        def fetch(url, limit):
            self.calls.append(url)
            if urlsplit(url).hostname == 'api.panoramax.xyz':
                return json.dumps({"features": pictures}).encode()
            if offline and urlsplit(url).hostname == 'panoramax.openstreetmap.fr':
                raise OSError('unreachable instance')
            return b"\xff\xd8invented"
        service = sv.StreetImagery(self.temp.name, fetcher=fetch, clock=lambda: self.now)
        result = service.nearest(48.8576, 2.3494)
        self.assertEqual(len(result['pictures']), 8)
        self.assertIn('available', [p['id'] for p in result['pictures']])
        for photo_id in ('offline-0', 'offline-1'):
            with self.assertRaises(ValueError):
                service.image('panoramax', photo_id, 'sd')
        self.assertEqual(sum(urlsplit(url).hostname == 'panoramax.openstreetmap.fr' for url in self.calls), 1)
        self.assertTrue(service.image('panoramax', 'available', 'sd').startswith(b'\xff\xd8'))
        self.assertEqual(len(service.nearest(48.85761, 2.3494)['pictures']), 8)
        self.assertEqual(sum(urlsplit(url).hostname == 'api.panoramax.xyz' for url in self.calls), 2)
        self.now += 31
        offline = False
        self.assertTrue(service.image('panoramax', 'offline-0', 'sd').startswith(b'\xff\xd8'))

    def test_invalid_coordinates_asset_hosts_and_traversal_are_refused(self):
        for lat, lng in ((float('nan'), 2), (38, 181), (90, 0)):
            with self.assertRaises(ValueError):
                self.service().nearest(lat, lng)
        for url in ("http://127.0.0.1/a.jpg", "https://evil.example/a.jpg", "https://api.panoramax.xyz@evil.example/a", "file:///etc/passwd"):
            with self.assertRaises(ValueError):
                sv.safe_url(url)
        for photo_id in ("../secret", "/tmp/file", "%2e%2e"):
            with self.assertRaises(ValueError):
                self.service().image('panoramax', photo_id, 'sd')

    def test_disabled_service_route_and_no_startup_fetch(self):
        responses = []
        handler = SimpleNamespace(server=SimpleNamespace(streetview=None), headers={}, json=lambda *args: responses.append(args))
        self.assertTrue(sv.handle(handler, urlsplit('/api/streetview/nearest?lat=38&lng=-9')))
        self.assertEqual(responses[0][1], 503)
        self.service()
        self.assertEqual(self.calls, [])

    def test_mock_is_explicitly_invented(self):
        service = sv.MockStreetImagery(Path(__file__).with_name('upload-test.jpg'))
        photo = service.nearest(38, -9)['pictures'][0]
        self.assertEqual(photo['distance_m'], 12)
        self.assertEqual(photo['heading_deg'], 90)
        self.assertEqual(photo['attribution'], 'Invented mock image')
        self.assertTrue(service.image('mock', photo['id'], 'sd').startswith(b'\xff\xd8'))

    def test_public_image_redirect_is_validated_at_each_hop(self):
        target = 'https://panoramax-storage-public-fast.s3.gra.perf.cloud.ovh.net/example.jpg'
        opener = Mock()
        opener.open.side_effect = [HTTPError('https://panoramax.ign.fr/image', 302, 'Found', {'Location': target}, io.BytesIO()), io.BytesIO(b'\xff\xd8image')]
        public_dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('1.1.1.1', 443))]
        with patch.object(sv.socket, 'getaddrinfo', return_value=public_dns), patch.object(sv.urllib.request, 'build_opener', return_value=opener):
            self.assertEqual(sv.fetch('https://panoramax.ign.fr/image', 100), b'\xff\xd8image')
            self.assertEqual(opener.open.call_count, 2)
            opener.open.reset_mock()
            opener.open.side_effect = [HTTPError('https://panoramax.ign.fr/image', 302, 'Found', {'Location': 'https://127.0.0.1/secret'}, io.BytesIO())]
            with self.assertRaises(ValueError):
                sv.fetch('https://panoramax.ign.fr/image', 100)
            self.assertEqual(opener.open.call_count, 1)
