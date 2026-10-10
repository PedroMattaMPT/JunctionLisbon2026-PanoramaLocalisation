#!/usr/bin/env bash
# Build the OSV-5M reference photo bank in Data/osv5m/ (gitignored), in this order:
#   1. the whole PT/ES/FR test split (5,206 images, for evaluation only)
#   2. every PT training image (51,551)
#   3. a fixed random sample of ES and FR training images (25k each, mainland Europe only)
# Needs the id lists from `osv5m_subset.py filter` in Data/osv5m/lists/. Safe to re-run: finished
# shards and downloaded images are skipped.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
D="$ROOT/Data/osv5m"
L="$D/lists"
OSV="python3 -I $ROOT/tools/osv5m_subset.py"
WORKERS="${WORKERS:-24}"
mkdir -p "$D/index" "$D/images"

# Id lists. The ES/FR sample uses seed 0 and a mainland bbox, so it is the same on every machine.
python3 -I - "$L" <<'EOF'
import csv, gzip, random, sys
L = sys.argv[1]
def rows(name):
    with gzip.open(f'{L}/{name}', 'rt', newline='') as f:
        yield from csv.DictReader(f)
def write(name, ids):
    with open(f'{L}/{name}', 'w') as f:
        f.write('\n'.join(ids) + '\n')
write('ids_test.txt', [r['id'] for n in ('osv5m_test_PT.csv.gz', 'osv5m_test_ES_FR.csv.gz') for r in rows(n)])
write('ids_train_PT.txt', [r['id'] for r in rows('osv5m_train_PT.csv.gz')])
# The PT lists name the columns latitude/longitude, the ES/FR lists lat/lon.
lat = lambda r: float(r.get('lat') or r['latitude'])
lon = lambda r: float(r.get('lon') or r['longitude'])
mainland = lambda r: 35.0 <= lat(r) <= 51.5 and -10.0 <= lon(r) <= 10.0
esfr = [r for r in rows('osv5m_train_ES_FR.csv.gz') if mainland(r)]
rng = random.Random(0)
sample = []
for c in ('ES', 'FR'):
    pool = sorted(r['id'] for r in esfr if r['country'] == c)
    sample += rng.sample(pool, min(25000, len(pool)))
write('ids_train_ESFR_sample.txt', sample)
write('ids_train_all.txt', [r['id'] for r in rows('osv5m_train_PT.csv.gz')] + sample)
EOF

# Keep only the index rows whose id is in a list.
subset() {  # subset <index.csv> <ids.txt> <out.csv>
  python3 -I - "$@" <<'EOF'
import csv, sys
idx, ids, out = sys.argv[1:]
want = set(open(ids).read().split())
with open(idx, newline='') as f, open(out, 'w', newline='') as g:
    r = csv.DictReader(f); w = csv.DictWriter(g, r.fieldnames)
    w.writeheader(); w.writerows(x for x in r if x['id'] in want)
EOF
}

echo "### $(date -Is) test split"
$OSV index --split test --ids "$L/ids_test.txt" --out "$D/index/test.csv"
$OSV fetch --index "$D/index/test.csv" --dest "$D/images/test" --workers "$WORKERS"

echo "### $(date -Is) train index (98 shards)"
$OSV index --split train --ids "$L/ids_train_all.txt" --out "$D/index/train.csv"

echo "### $(date -Is) train PT"
subset "$D/index/train.csv" "$L/ids_train_PT.txt" "$D/index/train_PT.csv"
$OSV fetch --index "$D/index/train_PT.csv" --dest "$D/images/train_PT" --workers "$WORKERS"

echo "### $(date -Is) train ES/FR sample"
subset "$D/index/train.csv" "$L/ids_train_ESFR_sample.txt" "$D/index/train_ESFR.csv"
$OSV fetch --index "$D/index/train_ESFR.csv" --dest "$D/images/train_ESFR" --workers "$WORKERS"

echo "### $(date -Is) done"
