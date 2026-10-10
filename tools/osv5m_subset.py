#!/usr/bin/env python3
"""OSV-5M PT/ES/FR subset tools -- no need to download the 259 GB dataset.

Dataset: https://huggingface.co/datasets/osv5m/osv5m  (licence CC-BY-SA-4.0, keep attribution)

Sub-commands
  filter  Stream train.csv / test.csv from Hugging Face and keep only the rows of the given
          countries (gz CSV out; the 2.9 GB CSV is never written to disk).
  index   Read the ZIP central directory of each images/<split>/NN.zip with HTTP Range requests
          (~4.6 MB per 2.5 GB shard) and record where the wanted ids live.
  fetch   Download only those JPEGs, one ranged GET per image (members are STORED, i.e. uncompressed).

Measured 2026-10-10: shard train/05.zip central directory = 4 range requests / 4.6 MB / ~10 s;
one member ~1 s; PT/ES/FR images are spread evenly over all 98 train shards (~550 PT per shard).
Stored thumb_original_url values are expired (HTTP 403 "URL signature expired") -- use `id`
with the Mapillary Entity API if you need resolution above 512 px.

Examples
  python3 osv5m_subset.py filter --split train --countries PT,ES,FR --out osv5m_train_ptesfr.csv.gz
  python3 osv5m_subset.py index  --split train --ids osv5m_train_PT.csv.gz --out idx_train_PT.csv   # all 98 shards, resumable
  python3 osv5m_subset.py fetch  --index idx_train_PT.csv --dest imgs/ --workers 24
"""
import argparse
import csv
import gzip
import io
import os
import struct
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = 'https://huggingface.co/datasets/osv5m/osv5m/resolve/main'
N_SHARDS = {'train': 98, 'test': 5}
UA = {'User-Agent': 'osv5m-subset/1.0'}


def resolve(url):
    """Follow the HF redirect once; returns (final_url, size)."""
    req = urllib.request.Request(url, method='HEAD', headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.geturl(), int(r.headers['Content-Length'])


def range_get(url, start, end, retries=5):
    for k in range(retries):
        try:
            req = urllib.request.Request(url, headers={**UA, 'Range': f'bytes={start}-{end}'})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError) as e:
            if k == retries - 1:
                raise
            time.sleep(2 ** k)


class HttpRangeFile(io.RawIOBase):
    """Seekable read-only file over HTTP Range (enough for zipfile to read the central directory)."""

    def __init__(self, url):
        self.url, self.size = resolve(url)
        self.pos = 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def readinto(self, b):
        if self.pos >= self.size or len(b) == 0:
            return 0
        end = min(self.pos + len(b), self.size) - 1
        data = range_get(self.url, self.pos, end)
        b[:len(data)] = data
        self.pos += len(data)
        return len(data)


def load_ids(path):
    """Accepts a (gz) CSV with an 'id' column, or a text file with one id per line."""
    op = gzip.open if path.endswith('.gz') else open
    with op(path, 'rt', newline='') as f:
        first = f.readline()
        f.seek(0)
        if 'id' in first.split(','):
            return {row['id'] for row in csv.DictReader(f)}
        return {line.strip() for line in f if line.strip()}


def cmd_filter(a):
    csv.field_size_limit(10 ** 9)
    keep = set(a.countries.split(','))
    n = k = 0
    t = time.time()
    with urllib.request.urlopen(urllib.request.Request(f'{BASE}/{a.split}.csv', headers=UA), timeout=120) as r:
        rd = csv.DictReader(io.TextIOWrapper(r, encoding='utf-8', newline=''))
        cols = [c for c in rd.fieldnames if c not in ('thumb_original_url',)]
        with gzip.open(a.out, 'wt', newline='', compresslevel=6) as f:
            w = csv.DictWriter(f, cols, extrasaction='ignore')
            w.writeheader()
            for row in rd:
                n += 1
                if row['country'] in keep:
                    w.writerow(row)
                    k += 1
                if a.max_rows and n >= a.max_rows:
                    break
    print(f'{a.split}: scanned {n:,} rows, kept {k:,} ({",".join(sorted(keep))}) -> {a.out} in {time.time()-t:.0f}s')


def cmd_index(a):
    want = load_ids(a.ids)
    shards = range(N_SHARDS[a.split]) if a.shards == 'all' else [int(s) for s in a.shards.split(',')]
    done = set()
    new = not os.path.exists(a.out)
    if not new:
        with open(a.out, newline='') as f:
            done = {(r['split'], int(r['shard'])) for r in csv.DictReader(f)}
    with open(a.out, 'a', newline='') as f:
        w = csv.writer(f)
        if new:
            w.writerow(['id', 'split', 'shard', 'header_offset', 'size', 'compress_type', 'name'])
        for s in shards:
            if (a.split, s) in done:
                continue
            t = time.time()
            z = zipfile.ZipFile(io.BufferedReader(HttpRangeFile(f'{BASE}/images/{a.split}/{s:02d}.zip'), buffer_size=1 << 20))
            hits = 0
            for zi in z.infolist():
                if zi.is_dir():
                    continue
                iid = os.path.splitext(os.path.basename(zi.filename))[0]
                if iid in want:
                    w.writerow([iid, a.split, s, zi.header_offset, zi.compress_size, zi.compress_type, zi.filename])
                    hits += 1
            f.flush()
            print(f'{a.split}/{s:02d}.zip: {hits} wanted images ({time.time()-t:.1f}s)', flush=True)
    # note: a shard with 0 hits is not recorded, so it is re-read on resume (cheap).


_url_cache = {}
_url_lock = threading.Lock()


def shard_url(split, shard, refresh=False):
    key = (split, shard)
    with _url_lock:
        if refresh or key not in _url_cache:
            _url_cache[key] = resolve(f'{BASE}/images/{split}/{shard:02d}.zip')[0]
        return _url_cache[key]


def fetch_one(row, dest):
    path = os.path.join(dest, f"{row['id']}.jpg")
    if os.path.exists(path):
        return 'skip'
    off, size, ctype = int(row['header_offset']), int(row['size']), int(row['compress_type'])
    guess = 30 + len(row['name'].encode()) + 64          # local header + name + small extra field
    for attempt in range(2):
        url = shard_url(row['split'], int(row['shard']), refresh=attempt > 0)
        try:
            buf = range_get(url, off, off + guess + size - 1)
            break
        except urllib.error.HTTPError as e:              # signed CDN URL expired -> re-resolve once
            if e.code in (401, 403) and attempt == 0:
                continue
            raise
    if buf[:4] != b'PK\x03\x04':
        raise ValueError(f"bad local header for {row['id']}")
    n, m = struct.unpack('<HH', buf[26:30])
    start = 30 + n + m
    if len(buf) < start + size:
        buf += range_get(url, off + len(buf), off + start + size - 1)
    data = buf[start:start + size]
    if ctype == 8:
        data = zlib.decompressobj(-15).decompress(data)
    with open(path + '.part', 'wb') as f:
        f.write(data)
    os.replace(path + '.part', path)
    return 'ok'


def cmd_fetch(a):
    os.makedirs(a.dest, exist_ok=True)
    with open(a.index, newline='') as f:
        rows = list(csv.DictReader(f))
    if a.limit:
        rows = rows[:a.limit]
    t = time.time()
    ok = err = 0
    with ThreadPoolExecutor(a.workers) as ex:
        futs = [ex.submit(fetch_one, r, a.dest) for r in rows]
        for i, fu in enumerate(as_completed(futs), 1):
            try:
                fu.result()
                ok += 1
            except Exception as e:  # keep going, report at the end
                err += 1
                print('error:', e, file=sys.stderr)
            if i % 1000 == 0:
                print(f'{i:,}/{len(rows):,} done ({i/(time.time()-t):.1f} img/s)', flush=True)
    print(f'fetched {ok:,} ok, {err:,} errors in {time.time()-t:.0f}s -> {a.dest}')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest='cmd', required=True)
    f = sp.add_parser('filter')
    f.add_argument('--split', choices=['train', 'test'], default='train')
    f.add_argument('--countries', default='PT,ES,FR')
    f.add_argument('--out', required=True)
    f.add_argument('--max-rows', type=int, default=0, help='stop after N rows (testing)')
    i = sp.add_parser('index')
    i.add_argument('--split', choices=['train', 'test'], default='train')
    i.add_argument('--ids', required=True, help='CSV(.gz) with an id column, or one id per line')
    i.add_argument('--shards', default='all', help="'all' or e.g. 0,1,2")
    i.add_argument('--out', required=True)
    g = sp.add_parser('fetch')
    g.add_argument('--index', required=True)
    g.add_argument('--dest', required=True)
    g.add_argument('--workers', type=int, default=16)
    g.add_argument('--limit', type=int, default=0)
    a = p.parse_args()
    {'filter': cmd_filter, 'index': cmd_index, 'fetch': cmd_fetch}[a.cmd](a)


if __name__ == '__main__':
    main()
