#!/usr/bin/env bash
# Download the geographic assets of PLAN.md 4.4 into Data/geo/ (gitignored), most urgent first:
#   1. GeoNames places and postcodes for PT, ES, FR, plus the admin-code tables (name index)
#   2. CAOP 2025, the official Portuguese boundaries: mainland, Azores, Madeira (zone questions)
#   3. geoBoundaries outlines: PT country; ES and FR country, regions, provinces/départements
#   4. GHSL settlement model (SMOD, 1 km, 2025): coarse urbanity for the grid prior
#   5. OpenStreetMap extracts from Geofabrik: Portugal now, then Spain and France (~7 GB, md5-checked)
#   6. Copernicus DEM GLO-90 tiles over PT, ES, FR, islands included (elevation for the grid prior)
# Each finished file is logged with its date, size and URL in Data/geo/downloads.log.
# Safe to re-run: finished files are skipped and partial ones resume.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
G="$ROOT/Data/geo"
UA="JunctionLisbon2026-PanoramaLocalisation/0.1 (hackathon research)"
mkdir -p "$G"

get() {  # get <url> <dest>: resumable download, skipped when <dest> already exists
  [[ -s "$2" ]] && return 0
  mkdir -p "$(dirname "$2")"
  curl -fsSL --retry 8 --retry-all-errors --retry-delay 5 -C - -A "$UA" -o "$2.part" "$1"
  mv "$2.part" "$2"
  echo "$(date -Is) $(stat -c %s "$2") $1" >> "$G/downloads.log"
}

unpack() {  # unpack <zip> <dir>: extract once into its own directory
  [[ -d "$2" ]] || { unzip -q "$1" -d "$2.part" && mv "$2.part" "$2"; }
}

echo "### $(date -Is) GeoNames"
for c in PT ES FR; do
  get "https://download.geonames.org/export/dump/$c.zip" "$G/geonames/places/$c.zip"
  get "https://download.geonames.org/export/zip/$c.zip" "$G/geonames/postcodes/$c.zip"
  unpack "$G/geonames/places/$c.zip" "$G/geonames/places/$c"
  unpack "$G/geonames/postcodes/$c.zip" "$G/geonames/postcodes/$c"
done
for f in admin1CodesASCII.txt admin2Codes.txt featureCodes_en.txt; do
  get "https://download.geonames.org/export/dump/$f" "$G/geonames/$f"
done

echo "### $(date -Is) CAOP 2025"
for part in Continente RAA RAM; do
  get "https://geo2.dgterritorio.gov.pt/caop/CAOP_${part}_2025-gpkg.zip" "$G/boundaries/caop/CAOP_${part}_2025-gpkg.zip"
  unpack "$G/boundaries/caop/CAOP_${part}_2025-gpkg.zip" "$G/boundaries/caop/$part"
done

echo "### $(date -Is) geoBoundaries"
for spec in PRT/ADM0 ESP/ADM0 ESP/ADM1 ESP/ADM2 FRA/ADM0 FRA/ADM1 FRA/ADM2; do
  out="$G/boundaries/geoboundaries/${spec/\//-}.geojson"
  [[ -s "$out" ]] && continue
  url="$(curl -fsSL --retry 5 -A "$UA" "https://www.geoboundaries.org/api/current/gbOpen/$spec/" \
    | python3 -I -c 'import json, sys; print(json.load(sys.stdin)["gjDownloadURL"])')"
  get "$url" "$out"
done

echo "### $(date -Is) GHSL SMOD"
get "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_SMOD_GLOBE_R2023A/GHS_SMOD_E2025_GLOBE_R2023A_54009_1000/V2-0/GHS_SMOD_E2025_GLOBE_R2023A_54009_1000_V2_0.zip" \
    "$G/ghsl/GHS_SMOD_E2025_1000m.zip"
unpack "$G/ghsl/GHS_SMOD_E2025_1000m.zip" "$G/ghsl/smod"

osm() {  # osm <region>: Geofabrik extract, verified against its published md5
  local f="$G/osm/$1-latest.osm.pbf" want
  for attempt in 1 2; do
    get "https://download.geofabrik.de/europe/$1-latest.osm.pbf" "$f"
    want="$(curl -fsSL --retry 5 -A "$UA" "https://download.geofabrik.de/europe/$1-latest.osm.pbf.md5" | cut -d' ' -f1)"
    if [[ "$(md5sum "$f" | cut -d' ' -f1)" == "$want" ]]; then
      echo "$want  $1-latest.osm.pbf" > "$f.md5"
      return 0
    fi
    echo "md5 mismatch for $1 (the extract was probably updated mid-download), fetching again"
    rm -f "$f" "$f.md5"
  done
  echo "md5 still wrong for $1" >&2
  return 1
}

dem() {  # dem <W,S,E,N>...: the GLO-90 tiles covering the boxes that exist in the bucket
  local B="https://copernicus-dem-90m.s3.amazonaws.com"
  get "$B/tileList.txt" "$G/dem/tileList.txt"
  python3 -I - "$G/dem/tileList.txt" "$@" <<'EOF' | while read -r t; do get "$B/$t/$t.tif" "$G/dem/glo90/$t.tif"; done
import math, sys
have = set(open(sys.argv[1]).read().split())
for box in sys.argv[2:]:
    w, s, e, n = map(float, box.split(','))
    for lat in range(math.floor(s), math.floor(n) + 1):
        for lon in range(math.floor(w), math.floor(e) + 1):
            t = (f"Copernicus_DSM_COG_30_{'N' if lat >= 0 else 'S'}{abs(lat):02d}_00_"
                 f"{'E' if lon >= 0 else 'W'}{abs(lon):03d}_00_DEM")
            if t in have:
                print(t)
EOF
}

echo "### $(date -Is) OSM Portugal"
osm portugal
echo "### $(date -Is) DEM Portugal (mainland, Madeira, Azores)"
dem -9.6,36.9,-6.1,42.2 -17.3,32.6,-16.2,33.2 -31.5,36.9,-24.9,39.8
echo "### $(date -Is) OSM Spain"
osm spain
echo "### $(date -Is) OSM France"
osm france
echo "### $(date -Is) DEM Spain (mainland, Balearics, Canaries) and France (mainland, Corsica)"
dem -9.4,35.9,4.4,43.9 -18.2,27.6,-13.4,29.5 -5.2,41.3,9.6,51.1
echo "### $(date -Is) done"
du -sh "$G"/*
