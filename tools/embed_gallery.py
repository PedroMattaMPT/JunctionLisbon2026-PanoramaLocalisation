#!/usr/bin/env python3
"""Embed the Commons landmark gallery with PE-Core (TASKS.md T33; PLAN.md 4.5) -> Data/gallery/emb/.

Input: Data/gallery/commons/{PT,ES,FR}/manifest.csv, written by tools/fetch_commons.py, and the photos
it lists (<QID>.jpg, the item's P18 at 500 px). The download may still be running: fetch_commons
replaces each manifest atomically, and this script only reads it.

Incremental: a run embeds the manifest rows that no shard holds yet and appends them as new shards,
so rerunning the script follows the download. A shard is only rewritten to add its `hub` column (or
with --rehub). A photo that cannot be decoded is left out, listed in skipped.csv and tried again on
the next run. A lock file stops two runs from writing at once.
  shard_NNNNN.npz  key ("<CC>/<QID>"), emb (N x 1024 float16, L2-normalised), version, and per row:
                   qid, country, lat, lon (the item's P625), name, types, type_labels, heritage,
                   sitelinks, commons_file, commons_page, other_qids, photo (path under
                   Data/gallery/commons/), type_role, extent_m, extent_rule, hub
  manifest.json    model, preprocessing, version, shard list with row counts, per-country totals,
                   the last run's throughput
  skipped.csv      the photos the last run could not decode, with the error

Model and preprocessing come from panoloc.retrieval.PECore, the code that embeds the OSV-5M bank and
the panorama views, so a photo and a view are compared in the same space (EMBED_VERSION: the whole
photo squashed to 336 x 336, as for the bank).

The coordinates are the Wikidata item's P625: the landmark or the centre of the place, never the
camera. Each row's extent is the radius the name index assumes for the item's P31 types:
tools/build_name_index.py's WikidataRoles and WIKIDATA_RULES, imported read-only, so a gallery hit
and a name hit on the same item carry the same extent. Items whose types are only events, or that no
rule matches, get WIKIDATA_DEFAULT (a 100 m landmark). type_role keeps the rule's role (`landmark` or
`area`); panoloc.landmarks still returns every hit as a landmark candidate. The name is the item's
label in the country's language, else English, else the first label found (Wikidata extract).

Hubness. Some photos (a generic street, a village overview, a field) resemble every road scene and
would top the search for unrelated panoramas. `hub` is the photo's mean cosine similarity to its
HUB_K nearest neighbours among a fixed sample of OSV-5M `train` photos (HUB_SAMPLE rows, seed
HUB_SEED; never val or test): how much it looks like generic street imagery. panoloc.landmarks
subtracts it from the similarity (CSLS, Conneau et al. 2018). The reference sample is recorded in
the manifest; changing it means --rehub.

Usage (from the repo root; HF_HUB_OFFLINE=1 is set by the script):
  .venv/bin/python tools/embed_gallery.py                  # embed what is new, then verify
  .venv/bin/python tools/embed_gallery.py --bench 512      # throughput only, writes nothing
  .venv/bin/python tools/embed_gallery.py --verify
  setsid nohup .venv/bin/python tools/embed_gallery.py >> Data/gallery/emb/embed.log 2>&1 &
  .venv/bin/python tools/embed_gallery.py --rehub          # recompute every shard's hub column
Options: --batch 64 --workers 4 --shard-size 4096 --countries PT,ES,FR --limit N (testing)
"""
import argparse
import csv
import datetime
import fcntl
import gzip
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from panoloc.retrieval import EMBED_DIM, EMBED_VERSION, MODEL_ID, PREPROCESS  # noqa: E402

COMMONS_DIR = ROOT / "Data" / "gallery" / "commons"
OUT_DIR = ROOT / "Data" / "gallery" / "emb"
WIKIDATA = ROOT / "Data" / "wikidata" / "wikidata_ptesfr.csv.gz"
COUNTRIES = ("PT", "ES", "FR")
LABEL_ORDER = {"PT": ("pt", "en", "es", "fr", "mul"), "ES": ("es", "en", "ca", "gl", "eu", "pt", "fr", "mul"),
               "FR": ("fr", "en", "es", "ca", "eu", "pt", "mul")}
TEXT_COLUMNS = ("key", "qid", "country", "name", "types", "type_labels", "heritage", "commons_file",
                "commons_page", "other_qids", "photo", "type_role", "extent_rule")
SHARD_GLOB = "shard_[0-9][0-9][0-9][0-9][0-9].npz"
HUB_K = 10
HUB_SAMPLE = 60_000
HUB_SEED = 0


def shard_paths(out):
    return sorted(Path(out).glob(SHARD_GLOB))


def done_keys(out):
    """Keys of every photo already in a shard, after checking each shard's embedding version."""
    keys = set()
    for p in shard_paths(out):
        with np.load(p) as z:
            if str(z["version"]) != EMBED_VERSION:
                sys.exit(f"{p.name} holds {z['version']} embeddings, this code makes {EMBED_VERSION}: "
                         f"embed into a fresh --out")
            keys.update(z["key"].tolist())
    return keys


def manifest_rows(countries, commons=COMMONS_DIR):
    """Manifest rows of the photos on disk, in manifest order (fetch order: heritage, then sitelinks)."""
    rows = []
    for cc in countries:
        path = Path(commons) / cc / "manifest.csv"
        if not path.exists():
            continue
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if not r.get("file") or not r.get("qid"):
                    continue
                r["key"] = f"{cc}/{r['qid']}"
                r["rel"] = f"{cc}/{r['file']}"
                if (Path(commons) / r["rel"]).exists():
                    rows.append(r)
    return rows


def item_names(qids, path=WIKIDATA):
    """{qid: {lang: label}} for the given items, from the Wikidata extract (tools/fetch_wikidata.py)."""
    if not path.exists():
        print(f"no {path}: names left empty", flush=True)
        return {}
    want, out = set(qids), {}
    csv.field_size_limit(1 << 24)
    with gzip.open(path, "rt", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["qid"] in want:
                out[r["qid"]] = {k[6:]: v.strip() for k, v in r.items() if k.startswith("label_") and v and v.strip()}
    return out


def pick_name(labels, country):
    for lang in LABEL_ORDER.get(country, ("en",)):
        if labels.get(lang):
            return labels[lang]
    return next(iter(labels.values()), "")


def load_roles():
    """WikidataRoles of tools/build_name_index.py (read-only): the name index's per-type roles and extents."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_name_index", ROOT / "tools" / "build_name_index.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.WikidataRoles(), mod.WIKIDATA_DEFAULT


def classify(roles, default, row):
    """(type_role, extent_m, rule) of a manifest row; events-only items take the default."""
    qids = (row.get("types") or "").split("|")
    labels = (row.get("type_labels_en") or "").split("|")
    labels += [""] * (len(qids) - len(labels))
    got = roles.classify(labels, qids)
    if got is None:
        return default[1], float(default[2]), "events only: default"
    role, extent, rule = got
    return role, float(extent), rule


class Photos:
    """torch Dataset over gallery rows -> (preprocessed tensor, ok, error)."""

    def __init__(self, paths, preprocess):
        self.paths, self.preprocess = paths, preprocess

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, i):
        import torch
        from PIL import Image
        try:
            with Image.open(self.paths[i]) as im:
                return self.preprocess(im.convert("RGB")), True, ""
        except Exception as e:  # a truncated or odd file must not stop the run: it is skipped and retried
            return torch.zeros(3, *PREPROCESS["resize"]), False, f"{type(e).__name__}: {e}"[:200]


def embed_paths(model, paths, batch, workers):
    """-> (N x 1024 float16, N ok flags, N error strings)."""
    import torch
    ds = Photos([str(p) for p in paths], model.preprocess)
    dl = torch.utils.data.DataLoader(ds, batch_size=batch, num_workers=workers, pin_memory=True,
                                     prefetch_factor=4 if workers else None)
    embs, oks, errs = [], [], []
    for x, ok, err in dl:
        embs.append(model.embed_tensor(x).numpy().astype(np.float16))
        oks.append(ok.numpy())
        errs.extend(err)
    if not embs:
        return np.zeros((0, EMBED_DIM), np.float16), np.zeros(0, bool), []
    return np.concatenate(embs), np.concatenate(oks), errs


def shard_arrays(rows, emb, names, roles, default):
    cols = {c: [] for c in TEXT_COLUMNS}
    lat, lon, sitelinks, extent = [], [], [], []
    for r in rows:
        role, ext, rule = classify(roles, default, r)
        values = {"key": r["key"], "qid": r["qid"], "country": r["country"].split("|")[0] or r["key"][:2],
                  "name": pick_name(names.get(r["qid"], {}), r["key"][:2]), "types": r.get("types", ""),
                  "type_labels": r.get("type_labels_en", ""), "heritage": r.get("heritage_labels_en", ""),
                  "commons_file": r.get("commons_file", ""), "commons_page": r.get("commons_page", ""),
                  "other_qids": r.get("other_qids", ""), "photo": r["rel"], "type_role": role,
                  "extent_rule": f"wikidata type: {rule}"}
        for c in TEXT_COLUMNS:
            cols[c].append(values[c])
        lat.append(float(r["lat"]))
        lon.append(float(r["lon"]))
        sitelinks.append(int(r["sitelinks"]) if (r.get("sitelinks") or "").isdigit() else 0)
        extent.append(ext)
    arrays = {c: np.array(v, dtype=str) for c, v in cols.items()}
    arrays.update(lat=np.array(lat, np.float64), lon=np.array(lon, np.float64),
                  sitelinks=np.array(sitelinks, np.int32), extent_m=np.array(extent, np.float32),
                  emb=emb.astype(np.float16), version=np.array(EMBED_VERSION))
    return arrays


def hub_reference():
    """faiss index over a fixed sample of OSV-5M `train` embeddings, and its description."""
    import faiss
    from panoloc.retrieval import load_embeddings, read_manifest
    faiss.omp_set_num_threads(4)
    _, bank = load_embeddings(partitions=("train",), dtype=np.float16)
    sel = np.sort(np.random.default_rng(HUB_SEED).choice(len(bank), size=min(HUB_SAMPLE, len(bank)), replace=False))
    index = faiss.IndexFlatIP(EMBED_DIM)
    index.add(np.ascontiguousarray(bank[sel], dtype=np.float32))
    return index, {"reference": "OSV-5M train embeddings (Data/osv5m/emb)", "bank_written": read_manifest().get("written"),
                   "train_rows": len(bank), "sample": len(sel), "seed": HUB_SEED, "k": HUB_K,
                   "statistic": "mean cosine similarity to the k nearest reference photos"}


def add_hub(out, rehub=False):
    """Add the `hub` column to every shard without one (all shards with rehub). Returns the reference or None."""
    todo = []
    for p in shard_paths(out):
        with np.load(p) as z:
            if rehub or "hub" not in z.files:
                todo.append(p)
    if not todo:
        return None
    t0 = time.time()
    index, ref = hub_reference()
    for p in todo:
        with np.load(p) as z:
            arrays = {k: z[k] for k in z.files}
        sims, _ = index.search(np.ascontiguousarray(arrays["emb"], dtype=np.float32), HUB_K)
        arrays["hub"] = sims.mean(axis=1).astype(np.float32)
        tmp = p.with_name(p.stem + ".tmp.npz")
        np.savez(tmp, **arrays)
        tmp.replace(p)
    print(f"hub column added to {len(todo)} shards in {time.time() - t0:.0f} s", flush=True)
    return ref


def write_manifest(out, args, extra=None):
    import open_clip
    import torch
    shards, by_country = [], {}
    for p in shard_paths(out):
        with np.load(p) as z:
            shards.append({"file": p.name, "rows": int(len(z["key"]))})
            for cc, n in zip(*np.unique(z["country"], return_counts=True)):
                by_country[str(cc)] = by_country.get(str(cc), 0) + int(n)
    doc = {"model_id": MODEL_ID, "tower": "vision only (open_clip model.visual)", "embed_dim": EMBED_DIM,
           "dtype_stored": "float16", "normalised": "L2, computed in float32 before storage",
           "preprocess": PREPROCESS, "version": EMBED_VERSION,
           "source": "Data/gallery/commons/<CC>/manifest.csv (tools/fetch_commons.py)",
           "coordinates": "Wikidata P625 of the item: the landmark or place, never the camera",
           "extents": "tools/build_name_index.py WikidataRoles (assumed radius per P31 type)",
           "hub": "see the module docstring", "n_rows": sum(s["rows"] for s in shards), "by_country": by_country,
           "shards": shards,
           "torch": torch.__version__, "open_clip": open_clip.__version__, "batch": args.batch,
           "workers": args.workers, "written": datetime.datetime.now().isoformat(timespec="seconds"),
           **(extra or {})}
    tmp = out / "manifest.json.tmp"
    tmp.write_text(json.dumps(doc, indent=2))
    tmp.replace(out / "manifest.json")
    return doc


def previous_runs(out):
    """The hub reference and last run recorded by the previous manifest, if any."""
    try:
        doc = json.loads((Path(out) / "manifest.json").read_text())
    except (OSError, ValueError):
        return {}
    return {k: doc[k] for k in ("hub_reference", "last_run") if k in doc}


def verify(out):
    """Unique keys, unit norms, no NaN, finite WGS84 points, positive extents, one version."""
    keys, n_nan, norms, bad_pts, bad_ext, versions, no_hub = [], 0, [], 0, 0, set(), 0
    for p in shard_paths(out):
        with np.load(p) as z:
            e = z["emb"].astype(np.float32)
            keys.extend(z["key"].tolist())
            n_nan += int(np.isnan(e).sum())
            norms.append(np.linalg.norm(e, axis=1))
            lat, lon = z["lat"], z["lon"]
            bad_pts += int((~(np.isfinite(lat) & np.isfinite(lon) & (np.abs(lat) <= 90) & (np.abs(lon) <= 180))).sum())
            bad_ext += int((~(z["extent_m"] > 0)).sum())
            versions.add(str(z["version"]))
            no_hub += len(z["key"]) if "hub" not in z.files else int((~np.isfinite(z["hub"])).sum())
    norms = np.concatenate(norms) if norms else np.ones(1)
    report = {"shards": len(shard_paths(out)), "rows": len(keys), "unique_keys": len(set(keys)), "nan": n_nan,
              "norm_min": round(float(norms.min()), 4), "norm_max": round(float(norms.max()), 4),
              "bad_points": bad_pts, "bad_extents": bad_ext, "rows_without_hub": no_hub, "versions": sorted(versions)}
    print(json.dumps(report, indent=2))
    ok = (report["unique_keys"] == len(keys) and n_nan == 0 and bad_pts == 0 and bad_ext == 0 and no_hub == 0
          and abs(report["norm_min"] - 1) < 1e-2 and abs(report["norm_max"] - 1) < 1e-2
          and versions <= {EMBED_VERSION})
    print("VERIFIED" if ok else "FAILED", flush=True)
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--commons", type=Path, default=COMMONS_DIR)
    ap.add_argument("--countries", default=",".join(COUNTRIES))
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--shard-size", type=int, default=4096)
    ap.add_argument("--limit", type=int, default=0, help="embed at most this many new photos (testing)")
    ap.add_argument("--bench", type=int, default=0, help="embed this many photos, report img/s, write nothing")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--rehub", action="store_true", help="recompute the hub column of every shard")
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.verify:
        sys.exit(0 if verify(args.out) else 1)
    countries = [c for c in args.countries.split(",") if c]
    if set(countries) - set(COUNTRIES):
        sys.exit(f"--countries must be among {COUNTRIES}")

    lock = open(args.out / ".lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit("another embed_gallery run holds the lock")

    t_start = time.time()
    done = done_keys(args.out)
    rows = [r for r in manifest_rows(countries, args.commons) if r["key"] not in done]
    if args.bench:
        rows = rows[:args.bench] or manifest_rows(countries, args.commons)[:args.bench]
    elif args.limit:
        rows = rows[:args.limit]
    print(f"{datetime.datetime.now():%H:%M:%S} {len(done):,} photos already embedded, {len(rows):,} new", flush=True)
    if not rows and not args.bench:
        ref = add_hub(args.out, args.rehub)
        if ref:
            write_manifest(args.out, args, {**previous_runs(args.out), "hub_reference": ref})
            verify(args.out)
        return

    from panoloc.retrieval import PECore
    t0 = time.time()
    model = PECore()
    print(f"model loaded in {time.time() - t0:.1f} s on {model.device}", flush=True)

    if args.bench:
        import torch
        embed_paths(model, [args.commons / r["rel"] for r in rows[:args.batch]], args.batch, 0)  # warm-up
        torch.cuda.synchronize()
        t = time.time()
        _, ok, _ = embed_paths(model, [args.commons / r["rel"] for r in rows], args.batch, args.workers)
        dt = time.time() - t
        print(f"bench: {len(rows)} photos in {dt:.1f} s = {len(rows) / dt:.1f} img/s, {int((~ok).sum())} unreadable; "
              f"peak GPU {torch.cuda.max_memory_allocated() / 2**30:.2f} GiB")
        return

    roles, default = load_roles()
    names = item_names({r["qid"] for r in rows})
    print(f"names for {len(names):,} of {len(rows):,} items", flush=True)
    next_k = max([int(p.stem.split("_")[1]) for p in shard_paths(args.out)] + [-1]) + 1
    skipped, n_new, t_embed = [], 0, 0.0
    for i in range(0, len(rows), args.shard_size):
        part = rows[i:i + args.shard_size]
        t = time.time()
        emb, ok, errs = embed_paths(model, [args.commons / r["rel"] for r in part], args.batch, args.workers)
        t_embed += time.time() - t
        skipped += [(r["rel"], e) for r, o, e in zip(part, ok, errs) if not o]
        keep = [r for r, o in zip(part, ok) if o]
        name = "no shard"
        if keep:
            path = args.out / f"shard_{next_k:05d}.npz"
            tmp = path.with_name(path.stem + ".tmp.npz")
            np.savez(tmp, **shard_arrays(keep, emb[ok], names, roles, default))
            tmp.replace(path)
            name, next_k, n_new = path.name, next_k + 1, n_new + len(keep)
        print(f"{datetime.datetime.now():%H:%M:%S} {name}: {len(keep)} photos ({len(part) - len(keep)} unreadable) "
              f"in {time.time() - t:.0f} s, {len(part) / (time.time() - t):.1f} img/s", flush=True)
    with open(args.out / "skipped.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "error"])
        w.writerows(skipped)
    rate = (n_new + len(skipped)) / t_embed if t_embed else 0.0
    ref = add_hub(args.out, args.rehub) or previous_runs(args.out).get("hub_reference")
    doc = write_manifest(args.out, args, {"hub_reference": ref, "last_run": {
        "finished": datetime.datetime.now().isoformat(timespec="seconds"), "embedded": n_new,
        "unreadable": len(skipped), "img_per_s": round(rate, 1), "seconds": round(time.time() - t_start, 1),
        "rule_counts": dict(roles.rule_counts.most_common())}})
    print(f"embedded {n_new:,} photos ({len(skipped)} unreadable, see skipped.csv) at {rate:.1f} img/s; "
          f"gallery {doc['n_rows']:,} photos {doc['by_country']}", flush=True)
    verify(args.out)


if __name__ == "__main__":
    main()
