#!/usr/bin/env python3
"""Wikidata place/landmark extract for Portugal, Spain and France -> one gzipped CSV + provenance JSON.

Rows: every item with a coordinate (wdt:P625) whose country (wdt:P17) is Portugal (Q45), Spain (Q29)
or France (Q142), overseas France included. Truthy (best-rank) statements only. One row per item;
an item with several of these countries (border features) appears once with country "ES|FR".

Endpoint: QLever's Wikidata endpoint (https://qlever.dev/api/wikidata, full dump + live updates),
which streams exports of millions of rows. Each field is one SPARQL query per country (base rows,
sitelinks, types, type labels, labels, aliases, P18, P1435, P1435 labels, P131); the raw CSV results
are kept gzipped in <out>/raw/ and joined here in Python. Every export is checked against a COUNT of
the same query (the index updates live, so a difference under 0.5% is accepted and logged).

Columns of wikidata_ptesfr.csv.gz (multi-valued cells are joined with "|"; a literal "|" inside a
multi-valued text value is replaced by U+00A6 and counted in the provenance file; missing values stay empty):
  qid, country (PT|ES|FR), lat, lon        first coordinate after sorting by (lat, lon)
  n_coords, other_coords                   other truthy coordinates as "lat lon|lat lon"
  types, type_labels_en                    P31 QIDs and their English labels (same order; "" if none)
  label_<l>, aliases_<l>                   l in pt es fr en ca gl eu mul ("mul" = Wikidata's
                                           language-independent label, kept as its own column)
  image                                    P18 Commons file name(s), decoded, spaces kept
  sitelinks                                number of Wikimedia sitelinks
  heritage, heritage_labels_en             P1435 heritage designation QIDs and English labels
  located_in                               P131 QIDs
Coordinates mark the item (a landmark, a town centre), never a camera position.

Usage (from the repo root)
  python3 -I tools/fetch_wikidata.py --out Data/wikidata                 # resumable: reuses raw/
  python3 -I tools/fetch_wikidata.py --out Data/wikidata --countries PT  # one country only
  python3 -I tools/fetch_wikidata.py --out Data/wikidata --refresh       # re-run every query
"""
import argparse
import csv
import gzip
import http.client
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ENDPOINT = 'https://qlever.dev/api/wikidata'
UA = {'User-Agent': 'JunctionLisbon2026-PanoramaLocalisation/0.1 (hackathon research)'}
COUNTRIES = {'PT': 'Q45', 'ES': 'Q29', 'FR': 'Q142'}
LANGS = ['pt', 'es', 'fr', 'en', 'ca', 'gl', 'eu', 'mul']
WD = 'http://www.wikidata.org/entity/'
FILEPATH = 'http://commons.wikimedia.org/wiki/Special:FilePath/'
PREFIXES = """PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
"""
SCOPE = '?item wdt:P17 wd:{c} . ?item wdt:P625 ?coord .'
LANG_IN = ', '.join(f'"{l}"' for l in LANGS)
# name -> (SELECT clause, extra pattern). Every query is restricted to SCOPE.
QUERIES = {
    'base':            ('?item ?coord', ''),
    'sitelinks':       ('DISTINCT ?item ?sitelinks', '?item wikibase:sitelinks ?sitelinks .'),
    'types':           ('DISTINCT ?item ?type', '?item wdt:P31 ?type .'),
    'type_labels':     ('DISTINCT ?type ?label',
                        '?item wdt:P31 ?type . ?type rdfs:label ?l . FILTER(LANG(?l) = "en") BIND(STR(?l) AS ?label)'),
    'labels':          ('DISTINCT ?item ?lang ?label',
                        f'?item rdfs:label ?l . BIND(LANG(?l) AS ?lang) FILTER(?lang IN ({LANG_IN})) BIND(STR(?l) AS ?label)'),
    'aliases':         ('DISTINCT ?item ?lang ?label',
                        f'?item skos:altLabel ?l . BIND(LANG(?l) AS ?lang) FILTER(?lang IN ({LANG_IN})) BIND(STR(?l) AS ?label)'),
    'images':          ('DISTINCT ?item ?image', '?item wdt:P18 ?image .'),
    'heritage':        ('DISTINCT ?item ?heritage', '?item wdt:P1435 ?heritage .'),
    'heritage_labels': ('DISTINCT ?heritage ?label',
                        '?item wdt:P1435 ?heritage . ?heritage rdfs:label ?l . FILTER(LANG(?l) = "en") BIND(STR(?l) AS ?label)'),
    'located_in':      ('DISTINCT ?item ?located', '?item wdt:P131 ?located .'),
}
POINT = re.compile(r'^\s*POINT\s*\(\s*([-+0-9.eE]+)\s+([-+0-9.eE]+)\s*\)\s*$', re.I)
RETRY_HTTP = {429, 500, 502, 503, 504}


def log(msg):
    print(f'{datetime.now().strftime("%H:%M:%S")} {msg}', flush=True)


def build_query(name, c):
    sel, extra = QUERIES[name]
    return f'{PREFIXES}SELECT {sel} WHERE {{ {SCOPE.format(c=c)} {extra} }}'


def count_query(q):
    head, _, body = q.partition('SELECT ')
    return f'{head}SELECT (COUNT(*) AS ?n) WHERE {{ {{ SELECT {body} }} }}'


def post(endpoint, query, accept, timeout):
    data = urllib.parse.urlencode({'query': query}).encode()
    req = urllib.request.Request(endpoint, data=data, headers={**UA, 'Accept': accept,
                                 'Content-Type': 'application/x-www-form-urlencoded'})
    return urllib.request.urlopen(req, timeout=timeout)


def with_retries(fn, what, retries=7):
    """Retry on network errors (DNS, TLS hostname mismatch, resets, timeouts) and 429/5xx, never on 4xx."""
    for k in range(retries):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            body = e.read()[:2000].decode('utf-8', 'replace')
            if e.code not in RETRY_HTTP or k == retries - 1:
                raise RuntimeError(f'{what}: HTTP {e.code}: {body}') from None
            wait = int(e.headers.get('Retry-After') or 0) or 2 ** (k + 2)
            log(f'{what}: HTTP {e.code}, retry in {wait}s')
        except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
            if k == retries - 1:
                raise
            wait = 2 ** (k + 2)
            log(f'{what}: {type(e).__name__}: {e}, retry in {wait}s')
        time.sleep(wait)


def run_count(endpoint, q, what):
    def go():
        with post(endpoint, count_query(q), 'text/csv', 600) as r:
            rows = list(csv.reader(io.StringIO(r.read().decode('utf-8'))))
        return int(rows[1][0])
    return with_retries(go, f'{what} count')


def run_export(endpoint, q, path, what):
    """Stream the CSV result to path (gzip) through .part + rename; returns (rows, bytes, seconds)."""
    def go():
        t = time.time()
        nbytes = 0
        with post(endpoint, q, 'text/csv', 1800) as r, gzip.open(path + '.part', 'wb', compresslevel=6) as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                nbytes += len(chunk)
        with gzip.open(path + '.part', 'rt', encoding='utf-8', newline='') as f:
            rd = csv.reader(f)
            next(rd)
            rows = sum(1 for _ in rd)
        os.replace(path + '.part', path)
        return rows, nbytes, time.time() - t
    return with_retries(go, what)


def read_raw(path):
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as f:
        rd = csv.reader(f)
        next(rd)
        yield from rd


def qid(iri):
    return iri[len(WD):] if iri.startswith(WD) and iri[len(WD):][:1] == 'Q' else None


def clean(s, stats):
    if '|' in s:
        stats['pipe_replaced'] += 1
        s = s.replace('|', '¦')
    return s


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', required=True, help='output directory, e.g. Data/wikidata')
    p.add_argument('--countries', default='PT,ES,FR')
    p.add_argument('--endpoint', default=ENDPOINT)
    p.add_argument('--refresh', action='store_true', help='re-run queries even if raw/ files exist')
    p.add_argument('--tolerance', type=float, default=0.005, help='accepted relative export/count gap')
    a = p.parse_args()
    ccs = a.countries.split(',')
    raw = os.path.join(a.out, 'raw')
    os.makedirs(raw, exist_ok=True)
    t0 = time.time()
    started = datetime.now(timezone.utc).isoformat(timespec='seconds')

    def stats_info():
        try:
            with urllib.request.urlopen(urllib.request.Request(a.endpoint + '?cmd=stats', headers=UA), timeout=60) as r:
                s = json.load(r)
            return {k: s.get(k) for k in ('name-index', 'git-hash-index', 'git-hash-server', 'version-server',
                                          'num-triples-normal')}
        except Exception as e:  # provenance only
            return {'error': repr(e)}

    index_before = stats_info()
    log(f'endpoint {a.endpoint}: {index_before.get("name-index")}')

    # 1. queries -> raw/<CC>_<name>.csv.gz (skipped when present, unless --refresh)
    prov_q = []
    for cc in ccs:
        for name in QUERIES:
            q = build_query(name, COUNTRIES[cc])
            path = os.path.join(raw, f'{cc}_{name}.csv.gz')
            entry = {'country': cc, 'name': name, 'file': os.path.relpath(path, a.out), 'query': q}
            if os.path.exists(path) and not a.refresh:
                entry['reused'] = True
                entry['rows'] = sum(1 for _ in read_raw(path))
                log(f'{cc} {name}: reuse {entry["rows"]:,} rows')
            else:
                n_count = run_count(a.endpoint, q, f'{cc} {name}')
                rows, nbytes, secs = run_export(a.endpoint, q, path, f'{cc} {name}')
                gap = abs(rows - n_count) / max(n_count, 1)
                entry.update(rows=rows, count_query_rows=n_count, bytes=nbytes, seconds=round(secs, 1),
                             fetched_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'))
                log(f'{cc} {name}: {rows:,} rows (COUNT {n_count:,}), {nbytes/1e6:.1f} MB in {secs:.0f}s')
                if gap > a.tolerance:
                    os.remove(path)
                    sys.exit(f'{cc} {name}: export has {rows:,} rows but COUNT says {n_count:,}; removed, re-run')
            prov_q.append(entry)

    # 2. join
    stats = {'pipe_replaced': 0, 'coords_unparsed': 0, 'non_qid_values': 0}
    items = {}

    def rec(q):
        r = items.get(q)
        if r is None:
            r = items[q] = {'c': set(), 'xy': set(), 'types': set(), 'img': set(), 'her': set(), 'loc': set(),
                            'lab': {}, 'ali': {}, 'sl': ''}
        return r

    type_label, her_label = {}, {}
    for cc in ccs:
        f = lambda name: read_raw(os.path.join(raw, f'{cc}_{name}.csv.gz'))
        for it, coord in f('base'):
            q = qid(it)
            m = POINT.match(coord)
            if not q or not m:
                stats['coords_unparsed'] += 1
                continue
            r = rec(q)
            r['c'].add(cc)
            r['xy'].add((float(m.group(2)), float(m.group(1)), m.group(2), m.group(1)))
        for it, sl in f('sitelinks'):
            if (q := qid(it)) in items:
                items[q]['sl'] = sl
        for key, name in (('types', 'types'), ('her', 'heritage'), ('loc', 'located_in')):
            for it, v in f(name):
                if (q := qid(it)) in items:
                    vq = qid(v)
                    if vq:
                        items[q][key].add(vq)
                    else:
                        stats['non_qid_values'] += 1
        for it, img in f('images'):
            if (q := qid(it)) in items:
                name = urllib.parse.unquote(img[len(FILEPATH):] if img.startswith(FILEPATH) else img)
                items[q]['img'].add(name)
        for key, name in (('lab', 'labels'), ('ali', 'aliases')):
            for it, lang, text in f(name):
                if (q := qid(it)) in items:
                    d = items[q][key]
                    if key == 'lab':
                        d[lang] = text
                    else:
                        d.setdefault(lang, set()).add(clean(text, stats))
        for t, lab in f('type_labels'):
            if (tq := qid(t)):
                type_label[tq] = clean(lab, stats)
        for h, lab in f('heritage_labels'):
            if (hq := qid(h)):
                her_label[hq] = clean(lab, stats)

    # 3. write
    cols = (['qid', 'country', 'lat', 'lon', 'n_coords', 'other_coords', 'types', 'type_labels_en']
            + [f'label_{l}' for l in LANGS] + [f'aliases_{l}' for l in LANGS]
            + ['image', 'sitelinks', 'heritage', 'heritage_labels_en', 'located_in'])
    qkey = lambda q: int(q[1:])
    out = os.path.join(a.out, 'wikidata_ptesfr.csv.gz')
    order = [c for c in COUNTRIES if c in ccs]
    per_country = {cc: {'items': 0, 'with_p18': 0, 'with_heritage': 0} for cc in ccs}
    with gzip.open(out + '.part', 'wt', encoding='utf-8', newline='', compresslevel=6) as fo:
        w = csv.writer(fo)
        w.writerow(cols)
        for q in sorted(items, key=qkey):
            r = items[q]
            xy = sorted(r['xy'])
            types = sorted(r['types'], key=qkey)
            her = sorted(r['her'], key=qkey)
            for cc in r['c']:
                pc = per_country[cc]
                pc['items'] += 1
                pc['with_p18'] += bool(r['img'])
                pc['with_heritage'] += bool(her)
            w.writerow([q, '|'.join(c for c in order if c in r['c']), xy[0][2], xy[0][3], len(xy),
                        '|'.join(f'{p[2]} {p[3]}' for p in xy[1:]),
                        '|'.join(types), '|'.join(type_label.get(t, '') for t in types)]
                       + [r['lab'].get(l, '') for l in LANGS]
                       + ['|'.join(sorted(r['ali'].get(l, ()))) for l in LANGS]
                       + ['|'.join(sorted(r['img'])), r['sl'], '|'.join(her),
                          '|'.join(her_label.get(h, '') for h in her), '|'.join(sorted(r['loc'], key=qkey))])
    os.replace(out + '.part', out)

    multi = sum(1 for r in items.values() if len(r['c']) > 1)
    prov = {
        'description': 'Wikidata items with P625 and P17 in {Q45 Portugal, Q29 Spain, Q142 France}; truthy statements',
        'script': 'tools/fetch_wikidata.py',
        'endpoint': a.endpoint,
        'endpoint_index_before': index_before,
        'endpoint_index_after': stats_info(),
        'run_started_utc': started,
        'run_finished_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'run_seconds': round(time.time() - t0, 1),
        'output': os.path.basename(out),
        'output_bytes': os.path.getsize(out),
        'columns': cols,
        'unique_items': len(items),
        'items_in_several_countries': multi,
        'per_country': per_country,
        'distinct_types': len({t for r in items.values() for t in r['types']}),
        'cleaning': stats,
        'licence': 'Wikidata content is CC0',
        'queries': prov_q,
    }
    with open(os.path.join(a.out, 'provenance.json.part'), 'w') as f:
        json.dump(prov, f, indent=1, ensure_ascii=False)
    os.replace(os.path.join(a.out, 'provenance.json.part'), os.path.join(a.out, 'provenance.json'))
    log(f'{len(items):,} items ({multi:,} in several countries) -> {out} '
        f'({os.path.getsize(out)/1e6:.1f} MB) in {time.time()-t0:.0f}s')
    for cc, pc in per_country.items():
        log(f'  {cc}: {pc["items"]:,} items, {pc["with_p18"]:,} with P18, {pc["with_heritage"]:,} with P1435')


if __name__ == '__main__':
    main()
