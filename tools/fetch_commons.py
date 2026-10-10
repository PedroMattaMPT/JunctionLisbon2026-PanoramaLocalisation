#!/usr/bin/env python3
"""Wikimedia Commons landmark photos (Wikidata P18 thumbnails) for Portugal, Spain and France.

Input: the extract written by tools/fetch_wikidata.py (Data/wikidata/wikidata_ptesfr.csv.gz).
Output, one folder per country (Data/gallery/commons/<CC>/):
  Q<id>.jpg      500 px wide thumbnail (smaller originals are not upscaled by Wikimedia)
  plan.csv       ordered candidates (written by `plan`)
  manifest.csv   local file -> qid, Commons file, lat, lon, country, types, sitelinks, heritage ...
                 (rewritten by `fetch` and `verify` from plan.csv + the files on disk)
  failures.csv   files that could not be fetched, with the HTTP status / reason

Sub-commands
  plan    Candidates are items whose P18 is a .jpg/.jpeg file, minus maps, flags, coats of arms,
          diagrams and drawings (file-name keywords, see EXCLUDE). Each item goes to the folder of its
          first country in the order PT, ES, FR. ES/FR keep only the mainland-Europe box of the
          OSV-5M bank (35..51.5 N, 10 W..10 E: drops the Canaries and overseas France; PT keeps all).
          Order: heritage designation (P1435) first, then sitelinks (desc), then QID. A Commons file
          used by several items is fetched once, for the first item; the others go to other_qids.
          Prints the candidate count and the expected size per country.
  fetch   Download in plan order, round-robin over the given folders, until --cap files exist per
          folder (0 = all). Resumable: existing files are skipped, writes go through .part + rename,
          permanent failures in failures.csv are skipped unless --retry-failed.
  verify  Check every JPEG (starts FFD8, ends FFD9), rewrite manifest.csv, print counts and sizes.

Wikimedia rules followed (Robot policy https://wikitech.wikimedia.org/wiki/Robot_policy and the
User-Agent policy, both read 2026-10-10):
  - descriptive User-Agent with no personal data; TLS always verified
  - media servers: total concurrency <= 2 (two persistent connections), speed well under 25 Mbps
    (--max-mbps, default 8), only standard thumbnail widths (500 is one of 20 40 60 120 250 330 500
    960 1280 1920 3840, https://www.mediawiki.org/wiki/Common_thumbnail_sizes)
  - Wikimedia's 2026 rate limits (https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits): a User-Agent
    without contact info (email or full URL) is "Unidentified": 10 requests/min per IP, shared with everyone
    behind the same IP; on 2026-10-10 such requests got 429 "does not comply with our robot policy". So
    `fetch` refuses to run without --contact (a non-personal URL or email; env WIKIMEDIA_UA_CONTACT).
    A compliant User-Agent gets 200/min; the pace starts at --rps (0.25/s) and, after 100 clean responses,
    rises by 25% up to --max-rps (1/s)
  - the pace never returns to a level that was throttled; 200 throttles end the run
  - 429: wait Retry-After (at least 60 s) and halve the pace; 5 throttles within 10 min -> 15 min pause
  - 403: stop at once (looks like a block). 5xx: one retry after a 30 s pause, then a recorded failure
  - network errors (DNS, TLS hostname mismatch, resets, timeouts): exponential backoff, same file again
Coordinates are the Wikidata item's P625: the landmark or place, never a camera position.

Usage (from the repo root)
  python3 -I tools/fetch_commons.py plan   --extract Data/wikidata/wikidata_ptesfr.csv.gz --out Data/gallery/commons
  export WIKIMEDIA_UA_CONTACT=<non-personal URL or email>
  python3 -I tools/fetch_commons.py fetch  --dirs Data/gallery/commons/PT
  python3 -I tools/fetch_commons.py fetch  --dirs Data/gallery/commons/ES,Data/gallery/commons/FR --cap 30000
  sh tools/fetch_commons_all.sh            # the three steps above + verify, in the background (see the file)
  python3 -I tools/fetch_commons.py verify --dirs Data/gallery/commons/PT,Data/gallery/commons/ES,Data/gallery/commons/FR
"""
import argparse
import csv
import email.utils
import gzip
import hashlib
import http.client
import os
import random
import re
import signal
import ssl
import sys
import threading
import time
import urllib.parse
from collections import deque
from datetime import datetime, timezone

UA = 'JunctionLisbon2026-PanoramaLocalisation/0.1 (hackathon research)'
HOST = 'upload.wikimedia.org'
STANDARD_WIDTHS = (20, 40, 60, 120, 250, 330, 500, 960, 1280, 1920, 3840)
ORDER = ('PT', 'ES', 'FR')
ESFR_BOX = (35.0, -10.0, 51.5, 10.0)                      # S, W, N, E (same box as the OSV-5M ES/FR sample)
MEAN_THUMB_BYTES = 70_000                                  # 14 PT thumbnails at 500 px, measured 2026-10-10
EXCLUDE = re.compile(r'''\b(?:
    maps?|mapas?|mappa|karte|carte(?![\s-]+postales?)|locator|location\s+map|situation\s+map|
    localiza[cç][aã]o|localizaci[oó]n|situaci[oó]n|situa[cç][aã]o|
    (?<!primeiro\s)(?<!primer\s)(?<!segundo\s)plano\s+(?:de|del)|plan\s+of|planta\s+(?:baja|general)|
    flags?\s+of|bandeira\s+(?:de|do|da)|bandera\s+(?:de|del)|drapeau\s+(?:de|du|des)|bandiera|flagge|
    coat\s+of\s+arms|bras[aã]o|escudo|blas[oó]n|armoiries|wappen|stemma|her[aá]ldica|heraldry|armorial|
    diagram\w*|diagrama|sch[ée]ma|esquema|infographic|logo|logos|logotipo|logotype|pictogram\w*|
    engraving|gravure|grabado|gravura|litograf[ií]a|lithograph\w*|drawing|dibujo|desenho|dessin|croquis
)\b''', re.X | re.I)
PLAN_COLS = ['rank', 'file', 'qid', 'commons_file', 'lat', 'lon', 'country', 'types', 'type_labels_en',
             'sitelinks', 'heritage', 'heritage_labels_en', 'other_qids']
MANIFEST_COLS = PLAN_COLS[1:] + ['bytes', 'requested_width', 'source_url', 'commons_page', 'coord_source']
FAIL_COLS = ['file', 'qid', 'commons_file', 'reason', 'status', 'detail', 'time_utc']
PERMANENT = {'not_found', 'bad_request', 'not_jpeg', 'server_error'}
CTX = ssl.create_default_context()


def log(msg):
    print(f'{datetime.now().strftime("%m-%d %H:%M:%S")} {msg}', flush=True)


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def db_key(name):
    return name.replace(' ', '_')


def thumb_path(name, width):
    """MediaWiki's thumbnail URL path (FileRepo hash path, rawurlencode, 'thumbnail.<ext>' over 160 bytes)."""
    key = db_key(name)
    h = hashlib.md5(key.encode('utf-8')).hexdigest()
    enc = urllib.parse.quote(key, safe='')
    short = enc if len(key.encode('utf-8')) <= 160 else 'thumbnail.' + key.rsplit('.', 1)[-1].lower()
    return f'/wikipedia/commons/thumb/{h[0]}/{h[:2]}/{enc}/{width}px-{short}'


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def write_csv(path, cols, rows):
    with open(path + '.part', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, cols, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    os.replace(path + '.part', path)


# ---------------------------------------------------------------------------------------------- plan

def cmd_plan(a):
    st = {cc: dict(items=0, with_p18=0, no_jpeg=0, excluded_keyword=0, outside_box=0, duplicate_file=0)
          for cc in ORDER}
    cands = {cc: [] for cc in ORDER}
    excluded_examples = []
    with gzip.open(a.extract, 'rt', encoding='utf-8', newline='') as f:
        for r in csv.DictReader(f):
            cc = next(c for c in ORDER if c in r['country'].split('|'))
            s = st[cc]
            s['items'] += 1
            if not r['image']:
                continue
            s['with_p18'] += 1
            jpgs = [i for i in r['image'].split('|') if i.lower().endswith(('.jpg', '.jpeg'))]
            if not jpgs:
                s['no_jpeg'] += 1
                continue
            ok = [i for i in jpgs if not EXCLUDE.search(i.rsplit('.', 1)[0].replace('_', ' '))]
            if not ok:
                s['excluded_keyword'] += 1
                if len(excluded_examples) < 400:
                    excluded_examples.append(jpgs[0])
                continue
            lat, lon = float(r['lat']), float(r['lon'])
            if cc != 'PT' and not (a.box[0] <= lat <= a.box[2] and a.box[1] <= lon <= a.box[3]):
                s['outside_box'] += 1
                continue
            sl = int(r['sitelinks'] or 0)
            cands[cc].append(((0 if r['heritage'] else 1), -sl, int(r['qid'][1:]), r, ok[0]))
    for cc in ORDER:
        if not cands[cc]:
            continue
        cands[cc].sort(key=lambda t: t[:3])
        rows, by_file = [], {}
        for _, _, _, r, img in cands[cc]:
            key = db_key(img)
            if key in by_file:
                by_file[key]['other_qids'] = '|'.join(filter(None, [by_file[key]['other_qids'], r['qid']]))
                st[cc]['duplicate_file'] += 1
                continue
            row = {'rank': len(rows) + 1, 'file': f"{r['qid']}.jpg", 'qid': r['qid'], 'commons_file': img,
                   'lat': r['lat'], 'lon': r['lon'], 'country': r['country'], 'types': r['types'],
                   'type_labels_en': r['type_labels_en'], 'sitelinks': r['sitelinks'], 'heritage': r['heritage'],
                   'heritage_labels_en': r['heritage_labels_en'], 'other_qids': ''}
            by_file[key] = row
            rows.append(row)
        d = os.path.join(a.out, cc)
        os.makedirs(d, exist_ok=True)
        write_csv(os.path.join(d, 'plan.csv'), PLAN_COLS, rows)
        cap = a.cap.get(cc, 0)
        n = min(cap, len(rows)) if cap else len(rows)
        her = sum(1 for r in rows if r['heritage'])
        her_in = sum(1 for r in rows[:n] if r['heritage'])
        s = st[cc]
        log(f"{cc}: {s['items']:,} items, {s['with_p18']:,} with P18, {s['no_jpeg']:,} not JPEG, "
            f"{s['excluded_keyword']:,} map/flag/arms/diagram names, {s['outside_box']:,} outside box, "
            f"{s['duplicate_file']:,} shared files -> {len(rows):,} candidates ({her:,} heritage)")
        log(f"{cc}: plan {n:,} files{f' (cap {cap:,})' if cap else ''}, {her_in:,} heritage; expected "
            f"~{n * MEAN_THUMB_BYTES / 1e9:.2f} GB at ~{MEAN_THUMB_BYTES // 1000} KB per 500 px thumbnail "
            f"-> {os.path.join(d, 'plan.csv')}")
    if a.show_excluded:
        for e in excluded_examples[:a.show_excluded]:
            print('  excluded:', e)


# --------------------------------------------------------------------------------------------- fetch

class Pacer:
    """Paces request starts across workers; halves the pace on 429 and never returns to a throttled pace."""

    def __init__(self, rps, max_rps, max_bytes_per_s):
        self.lock = threading.Lock()
        self.interval = 1.0 / rps
        self.floor = 1.0 / max_rps                     # smallest interval allowed (fastest pace)
        self.ceiling = 60.0                            # slowest pace: one request per minute
        self.next_start = 0.0
        self.pause_until = 0.0
        self.clean = 0
        self.t429 = deque()
        self.window = deque()
        self.max_bytes_per_s = max_bytes_per_s
        self.throttles = 0
        self.starts = deque()

    def observed_interval(self):
        """Mean gap between request starts over the last 2 minutes (the real pace, set by latency too)."""
        now = time.monotonic()
        while self.starts and self.starts[0] < now - 120:
            self.starts.popleft()
        if len(self.starts) < 3:
            return self.interval
        return max(self.interval, (now - self.starts[0]) / len(self.starts))

    def wait(self, stop):
        while not stop.is_set():
            with self.lock:
                now = time.monotonic()
                while self.window and self.window[0][0] < now - 10:
                    self.window.popleft()
                t = max(self.next_start, self.pause_until)
                if sum(n for _, n in self.window) > self.max_bytes_per_s * 10:
                    t = max(t, self.window[0][0] + 10)
                if t <= now:
                    self.next_start = now + self.interval
                    self.starts.append(now)
                    return True
            time.sleep(min(t - now, 2.0))
        return False

    def ok(self, nbytes):
        with self.lock:
            self.window.append((time.monotonic(), nbytes))
            self.clean += 1
            if self.clean >= 100 and self.interval > self.floor:
                self.interval = max(self.floor, self.interval / 1.25)
                self.clean = 0

    def pause(self, seconds):
        with self.lock:
            self.pause_until = max(self.pause_until, time.monotonic() + seconds)

    def throttled(self, retry_after):
        with self.lock:
            now = time.monotonic()
            self.throttles += 1
            self.t429.append(now)
            while self.t429 and self.t429[0] < now - 600:
                self.t429.popleft()
            wait = max(retry_after, 60)
            if len(self.t429) >= 5:
                wait = max(wait, 900)
                self.t429.clear()
            cur = self.observed_interval()
            self.floor = max(self.floor, cur * 1.25)       # never as fast as the throttled pace again
            self.interval = min(self.ceiling, cur * 2)
            self.pause_until = max(self.pause_until, now + wait)
            self.clean = 0
            return wait, self.interval


def retry_after_seconds(v):
    if not v:
        return 0
    if v.strip().isdigit():
        return int(v.strip())
    try:
        return max(0, int(email.utils.parsedate_to_datetime(v).timestamp() - time.time()))
    except (TypeError, ValueError):
        return 0


def page_text(body):
    t = body.decode('utf-8', 'replace')
    t = re.sub(r'<style.*?</style>|<[^>]+>', ' ', t, flags=re.S)
    t = re.sub(r'Sensitive client information.*', '', t, flags=re.S)      # drops the echoed client IP
    return re.sub(r'\s+', ' ', t).strip()[:300]


def original_path(name):
    key = db_key(name)
    h = hashlib.md5(key.encode('utf-8')).hexdigest()
    return f'/wikipedia/commons/{h[0]}/{h[:2]}/{urllib.parse.quote(key, safe="")}'


ORIGINAL_MAX_BYTES = 3_000_000      # originals are only fetched when narrower than the thumbnail width


def is_complete_jpeg(b):
    return len(b) > 4 and b[:2] == b'\xff\xd8' and b[-2:] == b'\xff\xd9'


class Job:
    def __init__(self, a):
        self.a = a
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.pacer = Pacer(a.rps, a.max_rps, a.max_mbps * 1e6 / 8)
        self.dirs = a.dirs
        self.plans, self.have, self.inflight, self.iters, self.retry = {}, {}, {}, {}, {}
        self.failed, self.target = {}, {}
        self.n_ok = self.n_fail = self.bytes = 0
        self.t0 = time.time()
        self.notes = set()
        self.cache = {}
        self.ua = UA.replace('(hackathon research)', f'({a.contact}; hackathon research)')
        for d in self.dirs:
            plan = read_csv(os.path.join(d, 'plan.csv'))
            if not plan:
                sys.exit(f'{d}: no plan.csv, run `plan` first')
            self.plans[d] = plan
            self.failed[d] = {r['file']: r for r in read_csv(os.path.join(d, 'failures.csv'))}
            skip = set() if a.retry_failed else {f for f, r in self.failed[d].items() if r['reason'] in PERMANENT}
            present = {r['file'] for r in plan if os.path.exists(os.path.join(d, r['file']))}
            self.have[d] = len(present)
            self.inflight[d] = 0
            self.retry[d] = deque()
            self.iters[d] = iter([r for r in plan if r['file'] not in present and r['file'] not in skip])
            self.target[d] = min(a.cap, len(plan)) if a.cap else len(plan)
            log(f'{d}: {len(plan):,} planned, {self.have[d]:,} present, target {self.target[d]:,}, '
                f'{len(skip):,} permanent failures skipped')
        self.rr = 0

    def next_item(self):
        with self.lock:
            for k in range(len(self.dirs)):
                d = self.dirs[(self.rr + k) % len(self.dirs)]
                if self.have[d] + self.inflight[d] >= self.target[d]:
                    continue
                row = self.retry[d].popleft() if self.retry[d] else next(self.iters[d], None)
                if row is None:
                    continue
                self.inflight[d] += 1
                self.rr = (self.rr + k + 1) % len(self.dirs)
                return d, row
            return None

    def finish(self, d, row, ok, nbytes=0, requeue=False):
        with self.lock:
            self.inflight[d] -= 1
            if ok:
                self.have[d] += 1
                self.n_ok += 1
                self.bytes += nbytes
            elif requeue:
                self.retry[d].append(row)
            else:
                self.n_fail += 1

    def record_failure(self, d, row, reason, status='', detail=''):
        rec = {'file': row['file'], 'qid': row['qid'], 'commons_file': row['commons_file'], 'reason': reason,
               'status': status, 'detail': detail, 'time_utc': utcnow()}
        with self.lock:
            self.failed[d][row['file']] = rec
            write_csv(os.path.join(d, 'failures.csv'), FAIL_COLS, list(self.failed[d].values()))
        log(f'fail {row["file"]} {row["commons_file"][:70]!r}: {reason} {status} {detail[:120]}')

    def note_once(self, key, msg):
        if key not in self.notes:
            self.notes.add(key)
            log(msg)

    def get(self, conn, path, limit=None):
        """One GET on a persistent connection; returns (status, headers, body, conn)."""
        if conn is None:
            conn = http.client.HTTPSConnection(HOST, timeout=self.a.timeout, context=CTX)
        conn.request('GET', path, headers={'User-Agent': self.ua})
        r = conn.getresponse()
        clen = int(r.headers.get('Content-Length') or 0)
        if limit and clen > limit:
            conn.close()
            return r.status, r.headers, b'', None
        body = r.read()
        if r.will_close:
            conn.close()
            conn = None
        return r.status, r.headers, body, conn

    def worker(self):
        conn = None
        while not self.stop.is_set():
            item = self.next_item()
            if item is None:
                return
            d, row = item
            path = thumb_path(row['commons_file'], self.a.width)
            original = False
            net_tries = server_tries = throttles = bad_tries = 0
            while True:
                if not self.pacer.wait(self.stop):
                    self.finish(d, row, False, requeue=True)
                    return
                t_req = time.time()
                try:
                    status, hdrs, body, conn = self.get(conn, path, ORIGINAL_MAX_BYTES if original else None)
                except (OSError, http.client.HTTPException) as e:   # DNS, TLS, resets, timeouts
                    if conn is not None:
                        conn.close()
                    conn = None
                    net_tries += 1
                    if net_tries > self.a.net_retries:
                        self.finish(d, row, False)
                        self.record_failure(d, row, 'network', '', repr(e)[:200])
                        break
                    wait = min(300, 2 ** net_tries) * random.uniform(0.8, 1.2)
                    log(f'network error ({type(e).__name__}: {str(e)[:120]}), retry {row["file"]} in {wait:.0f}s')
                    time.sleep(wait)
                    continue
                self.rate_headers(hdrs)
                if self.a.verbose:
                    log(f'  {status} {time.time() - t_req:5.2f}s {len(body):7d}B {hdrs.get("x-cache-status")} '
                        f'rl={hdrs.get("x-ratelimit-remaining")} ra={hdrs.get("Retry-After")} {row["file"]}')
                if status == 200:
                    clen = hdrs.get('Content-Length')
                    if original and not body:
                        self.finish(d, row, False)
                        self.record_failure(d, row, 'bad_request', 200, f'original over {ORIGINAL_MAX_BYTES} B')
                        break
                    if (clen and int(clen) != len(body)) or not is_complete_jpeg(body):
                        bad_tries += 1
                        if bad_tries < 2:
                            continue
                        self.finish(d, row, False)
                        self.record_failure(d, row, 'not_jpeg', 200,
                                            f'{hdrs.get("Content-Type")} {len(body)}B head={body[:4].hex()}')
                        break
                    out = os.path.join(d, row['file'])
                    with open(out + '.part', 'wb') as f:
                        f.write(body)
                    os.replace(out + '.part', out)
                    if original:
                        with self.lock, open(os.path.join(d, 'originals.csv'), 'a', newline='') as f:
                            csv.writer(f).writerow([row['file'], row['commons_file'], len(body), utcnow()])
                    self.pacer.ok(len(body))
                    self.finish(d, row, True, len(body))
                    with self.lock:
                        cs = (hdrs.get('x-cache-status') or '?').split('-')[0]
                        self.cache[cs] = self.cache.get(cs, 0) + 1
                        if self.failed[d].pop(row['file'], None):
                            write_csv(os.path.join(d, 'failures.csv'), FAIL_COLS, list(self.failed[d].values()))
                    break
                if status == 429:
                    throttles += 1
                    wait, interval = self.pacer.throttled(retry_after_seconds(hdrs.get('Retry-After')))
                    self.note_once(('429', page_text(body)[:80]), f'429 body: {page_text(body)} | headers: ' + ', '.join(
                        f'{k}={v}' for k, v in hdrs.items() if k.lower() not in ('set-cookie', 'x-client-ip', 'nel', 'report-to')))
                    log(f'429 Too Many Requests (Retry-After {hdrs.get("Retry-After")!r}): pausing {wait:.0f}s, '
                        f'pace now 1 request / {interval:.1f}s, total throttles {self.pacer.throttles}')
                    if self.pacer.throttles >= self.a.max_throttles:
                        log(f'{self.pacer.throttles} throttles: stopping, try again later')
                        self.stop.set()
                    if throttles >= 3:
                        self.finish(d, row, False, requeue=True)
                        break
                    continue
                if status == 403:
                    log(f'403 body: {page_text(body)}')
                    log('403 Forbidden on the media server: stopping the whole run (possible block)')
                    self.stop.set()
                    self.finish(d, row, False, requeue=True)
                    break
                if status == 404:
                    self.finish(d, row, False)
                    self.record_failure(d, row, 'not_found', status, page_text(body)[:120])
                    break
                text = page_text(body)
                if not original and status in (400, 422, 500) and re.search(
                        r'bigger than the source|not scaled|larger than the (?:original|source)|upscal', text, re.I):
                    original = True                                  # original narrower than the width
                    path = original_path(row['commons_file'])
                    continue
                if status in (502, 503, 504) or (status >= 500 and 'thumbnail' not in text.lower()):
                    server_tries += 1
                    self.pacer.pause(30)
                    if server_tries < 2:
                        log(f'HTTP {status} for {row["file"]} ({text[:100]}), retry after a 30s pause')
                        continue
                if status >= 500:                                    # thumbnail render error: no retry
                    self.finish(d, row, False)
                    self.record_failure(d, row, 'server_error', status, text)
                    break
                self.finish(d, row, False)
                self.record_failure(d, row, 'bad_request', status, page_text(body))
                break
        if conn is not None:
            conn.close()

    def rate_headers(self, hdrs):
        """Pause until the window resets when x-ratelimit-remaining drops under 10% of the limit."""
        try:
            lim = int(hdrs.get('x-ratelimit-limit', '').split(',')[0])
            rem = int(hdrs.get('x-ratelimit-remaining', ''))
            reset = int(hdrs.get('x-ratelimit-reset', '') or 60)
        except ValueError:
            return
        if rem < lim * 0.1:
            self.note_once(('rl', rem // 1000), f'x-ratelimit-remaining {rem} of {lim}: pausing {reset}s')
            self.pacer.pause(reset + 1)

    def progress(self):
        el = max(1e-6, time.time() - self.t0)
        parts = [f'{os.path.basename(d.rstrip("/"))} {self.have[d]:,}/{self.target[d]:,}' for d in self.dirs]
        left = sum(max(0, self.target[d] - self.have[d]) for d in self.dirs)
        rate = self.n_ok / el
        eta = f'{left / rate / 3600:.1f} h' if rate > 0 else '?'
        log(f'progress {" | ".join(parts)} | +{self.n_ok:,} ok {self.n_fail:,} failed, {rate:.2f} img/s, '
            f'{self.bytes / 1e6:.0f} MB ({self.bytes / el / 1e3:.0f} KB/s), pace 1/{self.pacer.interval:.1f}s, '
            f'{self.pacer.throttles} throttles, cache {self.cache}, ETA {eta}')


def write_manifest(d, check=False):
    """Rewrite manifest.csv from plan.csv + files on disk; with check=True verify each JPEG first."""
    rows, bad, total = [], [], 0
    originals = set()
    if os.path.exists(os.path.join(d, 'originals.csv')):
        with open(os.path.join(d, 'originals.csv'), newline='') as f:
            originals = {r[0] for r in csv.reader(f) if r}
    for r in read_csv(os.path.join(d, 'plan.csv')):
        p = os.path.join(d, r['file'])
        if not os.path.exists(p):
            continue
        size = os.path.getsize(p)
        if check:
            with open(p, 'rb') as f:
                head = f.read(2)
                f.seek(max(0, size - 2))
                tail = f.read(2)
            if size < 4 or head != b'\xff\xd8' or tail != b'\xff\xd9':
                bad.append(r['file'])
                continue
        total += size
        orig = r['file'] in originals
        rows.append({**r, 'bytes': size, 'requested_width': 'original' if orig else WIDTH_USED[0],
                     'source_url': f'https://{HOST}' + (original_path(r['commons_file']) if orig else
                                                        thumb_path(r['commons_file'], WIDTH_USED[0])),
                     'commons_page': 'https://commons.wikimedia.org/wiki/File:' + urllib.parse.quote(db_key(r['commons_file'])),
                     'coord_source': 'wikidata_P625_item'})
    write_csv(os.path.join(d, 'manifest.csv'), MANIFEST_COLS, rows)
    return rows, bad, total


WIDTH_USED = [500]


def cmd_fetch(a):
    if a.width not in STANDARD_WIDTHS:
        sys.exit(f'--width {a.width} is not a standard Wikimedia thumbnail width {STANDARD_WIDTHS}')
    if a.workers > 2:
        sys.exit('the Wikimedia Robot policy allows at most 2 concurrent media requests')
    WIDTH_USED[0] = a.width
    if not re.search(r'https?://\S+\.\S+|\S+@\S+\.\S+', a.contact or ''):
        sys.exit('fetch needs --contact <full URL or email> (or env WIKIMEDIA_UA_CONTACT). Without contact info '
                 'Wikimedia rates the User-Agent "Unidentified" (10 requests/min per IP, shared by everyone behind '
                 'the venue IP) and answered on 2026-10-10 with 429 "Your request does not comply with our robot '
                 'policy". Use a non-personal contact (team address or project page).')
    job = Job(a)
    signal.signal(signal.SIGTERM, lambda *_: (log('SIGTERM: finishing in-flight requests'), job.stop.set()))
    log(f'start: {HOST}, width {a.width}px, {a.workers} workers, pace {a.rps * 60:.1f}/min (max {a.max_rps * 60:.1f}/min), '
        f'<= {a.max_mbps} Mbps, UA {job.ua!r}')
    threads = [threading.Thread(target=job.worker, daemon=True) for _ in range(a.workers)]
    for t in threads:
        t.start()
    last_p = last_m = time.time()
    done_at_m = 0
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(1)
            if job.stop.is_set():
                for t in threads:
                    t.join(timeout=120)
                break
            if time.time() - last_p >= a.progress_every:
                job.progress()
                last_p = time.time()
            if job.n_ok - done_at_m >= 500 or time.time() - last_m > 900:
                for d in job.dirs:
                    write_manifest(d)
                done_at_m, last_m = job.n_ok, time.time()
    except KeyboardInterrupt:
        log('interrupted: finishing in-flight requests')
        job.stop.set()
        for t in threads:
            t.join(timeout=90)
    job.progress()
    for d in job.dirs:
        rows, _, total = write_manifest(d)
        log(f'{d}: manifest {len(rows):,} files, {total / 1e9:.2f} GB')
    if job.stop.is_set():
        log('stopped early')
        sys.exit(2)
    log('done')


def cmd_verify(a):
    WIDTH_USED[0] = a.width
    g_ok = g_bad = g_bytes = 0
    for d in a.dirs:
        rows, bad, total = write_manifest(d, check=True)
        parts = [f for f in os.listdir(d) if f.endswith('.part')]
        plan = read_csv(os.path.join(d, 'plan.csv'))
        known = {r['file'] for r in plan}
        orphans = [f for f in os.listdir(d) if f.endswith('.jpg') and f not in known]
        fails = read_csv(os.path.join(d, 'failures.csv'))
        reasons = {}
        for r in fails:
            reasons[r['reason']] = reasons.get(r['reason'], 0) + 1
        log(f'{d}: {len(rows):,} complete JPEGs ({total / 1e9:.2f} GB, mean {total / max(1, len(rows)) / 1e3:.0f} KB), '
            f'{len(bad):,} incomplete, {len(parts)} .part, {len(orphans)} not in plan, '
            f'{len(fails):,} failures {reasons}, {len(plan):,} planned')
        for f in bad[:20]:
            log(f'  incomplete: {f}')
        if a.delete_bad:
            for f in bad + parts:
                os.remove(os.path.join(d, f))
        g_ok, g_bad, g_bytes = g_ok + len(rows), g_bad + len(bad), g_bytes + total
    log(f'total: {g_ok:,} complete, {g_bad:,} incomplete, {g_bytes / 1e9:.2f} GB')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest='cmd', required=True)
    pl = sp.add_parser('plan')
    pl.add_argument('--extract', required=True)
    pl.add_argument('--out', required=True, help='e.g. Data/gallery/commons')
    pl.add_argument('--cap', default='ES=30000,FR=30000', help='per-country cap shown in the estimate')
    pl.add_argument('--box', default=','.join(map(str, ESFR_BOX)), help='S,W,N,E box applied to ES/FR')
    pl.add_argument('--show-excluded', type=int, default=0, help='print N excluded file names')
    fe = sp.add_parser('fetch')
    fe.add_argument('--dirs', required=True, help='comma-separated country folders, fetched round-robin')
    fe.add_argument('--cap', type=int, default=0, help='stop at this many files per folder (0 = all)')
    fe.add_argument('--width', type=int, default=500)
    fe.add_argument('--workers', type=int, default=2)
    fe.add_argument('--rps', type=float, default=0.25, help='starting pace, requests per second (all workers)')
    fe.add_argument('--max-rps', type=float, default=1.0)
    fe.add_argument('--max-mbps', type=float, default=8.0)
    fe.add_argument('--max-throttles', type=int, default=200, help='stop the run after this many 429s')
    fe.add_argument('--net-retries', type=int, default=10)
    fe.add_argument('--timeout', type=float, default=90)
    fe.add_argument('--retry-failed', action='store_true')
    fe.add_argument('--progress-every', type=float, default=120, help='seconds between progress lines')
    fe.add_argument('--verbose', action='store_true', help='log every request')
    fe.add_argument('--contact', default=os.environ.get('WIKIMEDIA_UA_CONTACT', ''),
                    help='required: non-personal contact URL or email for the User-Agent '
                         '(env WIKIMEDIA_UA_CONTACT); Wikimedia requires it')
    ve = sp.add_parser('verify')
    ve.add_argument('--dirs', required=True)
    ve.add_argument('--width', type=int, default=500)
    ve.add_argument('--delete-bad', action='store_true', help='delete incomplete JPEGs and .part files')
    a = p.parse_args()
    if a.cmd == 'plan':
        a.cap = {k: int(v) for k, v in (kv.split('=') for kv in a.cap.split(',') if kv)}
        a.box = tuple(float(x) for x in a.box.split(','))
    else:
        a.dirs = [d for d in a.dirs.split(',') if d]
    {'plan': cmd_plan, 'fetch': cmd_fetch, 'verify': cmd_verify}[a.cmd](a)


if __name__ == '__main__':
    main()
