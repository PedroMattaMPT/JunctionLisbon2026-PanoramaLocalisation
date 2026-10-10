#!/bin/sh
# Commons landmark gallery, whole chain: all of Portugal, then Spain + France (30k each, round-robin),
# then verify. Resumable (existing files are skipped). Logs go next to the data in Data/gallery/commons/.
# Needs a non-personal contact for the Wikimedia User-Agent (see tools/fetch_commons.py).
# Run from the repo root:
#   WIKIMEDIA_UA_CONTACT=<URL or email> nohup sh tools/fetch_commons_all.sh > Data/gallery/commons/run_all.log 2>&1 &
# Stop gracefully: kill -TERM <python pid>   (SIGINT is ignored by background jobs)
set -u
: "${WIKIMEDIA_UA_CONTACT:?set WIKIMEDIA_UA_CONTACT to a non-personal URL or email}"
G=Data/gallery/commons
[ -f $G/PT/plan.csv ] || python3 -I tools/fetch_commons.py plan --extract Data/wikidata/wikidata_ptesfr.csv.gz --out $G >> $G/plan.log 2>&1
python3 -I tools/fetch_commons.py fetch --dirs $G/PT >> $G/fetch_PT.log 2>&1 \
  && python3 -I tools/fetch_commons.py fetch --dirs $G/ES,$G/FR --cap 30000 >> $G/fetch_ESFR.log 2>&1
rc=$?
python3 -I tools/fetch_commons.py verify --dirs $G/PT,$G/ES,$G/FR >> $G/verify.log 2>&1
echo "chain finished rc=$rc $(date -Is)"
