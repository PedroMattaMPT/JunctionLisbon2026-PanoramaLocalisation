#!/usr/bin/env python3
"""External test panoramas: 360-degree Panoramax pictures with GPS for PT, ES and FR (PLAN.md 4.6).

Pictures from one capture collection are near-duplicates, so the sample takes few per collection,
spreads them over 1-degree tiles, and assigns whole collections to `val` or `final`. No token needed.

Sub-commands
  list    Search 360-degree pictures tile by tile over a bbox (federated STAC API, one page per tile,
          so a busy tile is truncated at --per-tile; that is fine for sampling).
  sample  Keep pictures inside a country outline (GeoJSON), then pick --n of them round-robin over
          tiles, at most --per-collection from each collection. Seeded, so it is reproducible.
  fetch   Download the sampled pictures at full resolution ('hd'), resumable.

Licences are per picture (column `license`): CC-BY-SA-4.0 on the OSM-FR instance, etalab-2.0 on IGN.

Examples
  python3 -I tools/fetch_panoramax.py list --bbox=-9.55,36.95,-6.18,42.16 --out Data/panoramax/lists/PT.csv
  python3 -I tools/fetch_panoramax.py sample --list Data/panoramax/lists/PT.csv \
      --country Data/geo/boundaries/geoboundaries/PRT-ADM0.geojson --n 150 --per-collection 3 --out Data/panoramax/PT.csv
  python3 -I tools/fetch_panoramax.py fetch --sample Data/panoramax/PT.csv --dest Data/panoramax/images/PT
"""
import argparse
import csv
import http.client
import json
import math
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

API = 'https://api.panoramax.xyz/api/search'
UA = {'User-Agent': 'JunctionLisbon2026-PanoramaLocalisation/0.1 (hackathon research)'}
COLS = ['id', 'collection', 'lon', 'lat', 'datetime', 'camera_manufacturer', 'camera_model', 'width', 'height',
        'license', 'producer', 'hd', 'tile']


def get(url, timeout=120, retries=5):
    """GET with backoff on network errors, 429 and 5xx. A short body raises IncompleteRead."""
    for k in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.IncompleteRead) as e:
            permanent = isinstance(e, urllib.error.HTTPError) and e.code != 429 and e.code < 500
            if permanent or k == retries - 1:
                raise
            time.sleep(2 ** k)


def row(f, tile):
    p = f['properties']
    io = p.get('pers:interior_orientation') or {}
    dims = io.get('sensor_array_dimensions') or [None, None]
    coll = next((l['href'].rsplit('/', 1)[-1] for l in f.get('links', []) if l.get('rel') == 'collection'),
                f.get('collection'))
    return {'id': f['id'], 'collection': coll, 'lon': f['geometry']['coordinates'][0],
            'lat': f['geometry']['coordinates'][1], 'datetime': p.get('datetime'),
            'camera_manufacturer': io.get('camera_manufacturer'), 'camera_model': io.get('camera_model'),
            'width': dims[0], 'height': dims[1], 'license': p.get('license'), 'producer': p.get('geovisio:producer'),
            'hd': f.get('assets', {}).get('hd', {}).get('href'), 'tile': tile}


def cmd_list(a):
    w, s, e, n = map(float, a.bbox.split(','))
    tiles = [(x, y) for y in range(math.floor(s), math.ceil(n)) for x in range(math.floor(w), math.ceil(e))]
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    total = 0
    with open(a.out, 'w', newline='') as fo:
        wr = csv.DictWriter(fo, COLS)
        wr.writeheader()
        for i, (x, y) in enumerate(tiles):
            box = f'{max(x, w)},{max(y, s)},{min(x + 1, e)},{min(y + 1, n)}'
            q = {'bbox': box, 'limit': a.per_tile, 'filter': 'field_of_view=360'}
            feats = json.loads(get(API + '?' + urllib.parse.urlencode(q), timeout=300)).get('features', [])
            wr.writerows(row(f, f'{x},{y}') for f in feats if f.get('assets', {}).get('hd'))
            total += len(feats)
            print(f'tile {i + 1}/{len(tiles)} {box}: {len(feats)} pictures', flush=True)
    print(f'{total} pictures in {len(tiles)} tiles -> {a.out}')


def load_rings(path):
    """Polygon rings of a GeoJSON outline, each with its bbox, for an even-odd point-in-polygon test."""
    geo = json.load(open(path))
    feats = geo['features'] if geo.get('type') == 'FeatureCollection' else [geo]
    rings = []
    for f in feats:
        g = f.get('geometry', f)
        polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
        for poly in polys:
            for ring in poly:
                xs, ys = [p[0] for p in ring], [p[1] for p in ring]
                rings.append((min(xs), min(ys), max(xs), max(ys), ring))
    return rings


def inside(rings, x, y):
    hit = False
    for x0, y0, x1, y1, ring in rings:
        if not (x0 <= x <= x1 and y0 <= y <= y1):
            continue
        for (ax, ay), (bx, by) in zip(ring, ring[1:]):
            if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
                hit = not hit
    return hit


def cmd_sample(a):
    rows = list(csv.DictReader(open(a.list, newline='')))
    rng = random.Random(a.seed)
    rings = load_rings(a.country)
    by_tile = defaultdict(list)
    for r in rows:
        by_tile[r['tile']].append(r)
    for t in by_tile.values():
        rng.shuffle(t)
    tiles = sorted(by_tile)
    rng.shuffle(tiles)
    per_coll, seen, picked = {}, set(), []
    while len(picked) < a.n and any(by_tile[t] for t in tiles):
        for t in tiles:  # one picture per tile per round, so busy tiles cannot dominate
            while by_tile[t]:
                r = by_tile[t].pop()
                if r['id'] in seen or per_coll.get(r['collection'], 0) >= a.per_collection:
                    continue
                seen.add(r['id'])
                if inside(rings, float(r['lon']), float(r['lat'])):
                    per_coll[r['collection']] = per_coll.get(r['collection'], 0) + 1
                    picked.append(r)
                    break
            if len(picked) >= a.n:
                break
    colls = sorted(per_coll)
    rng.shuffle(colls)
    n_final = round(len(colls) * a.final_share)
    split = {c: ('final' if i < n_final else 'val') for i, c in enumerate(colls)}
    with open(a.out, 'w', newline='') as fo:
        wr = csv.DictWriter(fo, COLS + ['split'])
        wr.writeheader()
        wr.writerows({**r, 'split': split[r['collection']]} for r in picked)
    n_val = sum(split[r['collection']] == 'val' for r in picked)
    print(f'{len(picked)} pictures from {len(colls)} collections in {len({r["tile"] for r in picked})} tiles '
          f'(val {n_val}, final {len(picked) - n_val}) -> {a.out}')


def cmd_fetch(a):
    rows = list(csv.DictReader(open(a.sample, newline='')))
    os.makedirs(a.dest, exist_ok=True)

    def one(r):
        path = os.path.join(a.dest, f"{r['id']}.jpg")
        if os.path.exists(path):
            return 'skip'
        data = get(r['hd'], timeout=300)
        if data[:2] != b'\xff\xd8':  # cameras may append data after the JPEG end marker, so check the start only
            raise ValueError('not a JPEG')
        with open(path + '.part', 'wb') as f:
            f.write(data)
        os.replace(path + '.part', path)
        return 'ok'

    t, n, errors = time.time(), defaultdict(int), []
    with ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(one, r): r for r in rows}
        for i, fu in enumerate(as_completed(futs), 1):
            try:
                n[fu.result()] += 1
            except Exception as e:
                errors.append(f"{futs[fu]['id']}: {e}")
            if i % 25 == 0:
                print(f'{i}/{len(rows)} done, {len(errors)} errors, {time.time() - t:.0f}s', flush=True)
    for e in errors:
        print('ERROR', e)
    print(f"fetched {n['ok']}, skipped {n['skip']}, {len(errors)} errors in {time.time() - t:.0f}s -> {a.dest}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('list')
    p.add_argument('--bbox', required=True, help='W,S,E,N in degrees (write --bbox=... for negative values)')
    p.add_argument('--per-tile', type=int, default=100)
    p.add_argument('--out', required=True)
    p = sub.add_parser('sample')
    p.add_argument('--list', required=True)
    p.add_argument('--country', required=True, help='GeoJSON outline; pictures outside it are dropped')
    p.add_argument('--n', type=int, required=True)
    p.add_argument('--per-collection', type=int, default=1)
    p.add_argument('--final-share', type=float, default=1 / 3, help='share of collections reserved as final test')
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--out', required=True)
    p = sub.add_parser('fetch')
    p.add_argument('--sample', required=True)
    p.add_argument('--dest', required=True)
    p.add_argument('--workers', type=int, default=4)
    a = ap.parse_args()
    {'list': cmd_list, 'sample': cmd_sample, 'fetch': cmd_fetch}[a.cmd](a)


if __name__ == '__main__':
    main()
