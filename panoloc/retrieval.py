"""PE-Core embeddings and kNN retrieval over the OSV-5M photo bank (PLAN.md 3.2, 4.1; TASKS.md T21, T35, T36).

The bank is the OSV-5M images of tools/bank_partitions.py, embedded once by tools/embed_bank.py
(Data/osv5m/emb/: shards + manifest). Partitions: `train` and `val` form the default gallery, `test`
is the final external test and can never enter a Bank, `dropped` (Ceuta, Melilla) is left out.

Embeddings: PE-Core-L/14-336 vision tower (open_clip `hf-hub:timm/PE-Core-L-14-336`), float16 on the
GPU, L2-normalised in float32. PREPROCESS is open_clip's own transform for the checkpoint: the whole
image squashed to 336 x 336 (no crop), bilinear with antialiasing, mean = std = 0.5. PECore.embed
applies exactly the transform the bank was embedded with; EMBED_VERSION names it in the manifest.

A panorama is embedded as N_VIEWS = 12 horizontal views of VIEW_FOV = 60 degrees (panoloc.views.cut_views,
yaw 0, 30, ..., 330), cut at VIEW_SIZE px. On the Panoramax validation split, 12 x 60 degrees beat
8 x 90 degrees for kNN (non-urban score x10 2,479 vs 2,108; within 100 km 37.7% vs 28.5%; 8 x 75 and
8 x 60 in between) and tied for the region head (top-1 46.4% both, top-4 72.0% vs 73.9%): narrower
views look more like OSV-5M's phone and dashcam frames (runs/track2/fov_exp.json).
VIEW_CROP chooses what of each square view is embedded: "4:3" keeps the middle 3/4 of the rows, a
landscape frame like most OSV-5M photos (682 x 512) that also drops the lower corners where the
photographer stands; "square" keeps the whole view. "4:3" is the default: on the Panoramax validation
split, at the default tau, kNN scored 2,479 vs 2,288 (non-urban x10), and the region head was within
noise (top-1 46.4% vs 47.3%, top-4 72.0% vs 72.5%) (Data/osv5m/emb/eval_knn.json, Data/osv5m/head/report.json).

Search (Bank.search): per view, the PER_VIEW_K nearest bank images by cosine similarity. A neighbour
is scene resemblance, not a verified match: two roads can look alike hundreds of km apart, and only a
geometric check (MegaLoc + LightGlue, PLAN.md 3.3) can establish that the camera stood there.
Overlapping views see the same scene, and consecutive frames of one capture are near-duplicates, so
neighbours are merged before they count:
  1. Within a view, a group keeps its best neighbour: s_vg = max similarity of its images. A group is
     a PT sequence ("seq:...") or, for ES/FR (no sequence ids), a ~10 km block ("blk:row:col").
  2. Per view, the groups' kernel weights are normalised: p_vg = exp((s_vg - s_v,max) / tau) / sum_g ...
     Each view casts one vote; tau = TAU (cosine units) sets how sharply it prefers its best match.
     On Panoramax val, tau 0.02 / 0.05 / 0.1 scored within noise of each other (207 panoramas);
     0.05 is the middle choice.
  3. weight_g = (1/V) sum_v p_vg: the average of the per-view distributions over the V views, never
     a product (PLAN.md 3.2). A group missing from a view's neighbours gets 0 from that view.
The weights of all retrieved groups sum to 1: weight is the group's share of the panorama's
retrieval support, unnormalised for fusion purposes and not a calibrated probability. With one view
(a single photo) the order equals the order of the best similarity.

Each group becomes one Candidate at its best image (highest similarity over all views):
  role="camera" (OSV-5M GPS is where a camera stood), source="osv5m:<id>", group="pe-core",
  weight as above, accuracy_m=None (OSV-5M states no GPS accuracy), extent_m=None, country,
  details: similarity (best cosine), mean_similarity (over the views that retrieved it), views (names),
  n_views, n_images (its distinct images among the neighbours), ref_group (sequence or block),
  group_kind, region, partition, rank, note.
Every PE-Core source (this kNN, the RegionHead below) shares the "pe-core" group: fusion must cap
their combined influence (PLAN.md 3.2).

RegionHead (mini-PIGEON, PLAN.md 4.2) maps the same view embeddings to PT districts, ES communities
and FR regions; see its docstring.

  model = PECore()                                     # ~0.7 GB of GPU memory in float16
  pano = load_panorama(path)
  emb, names = embed_views(model, pano)                # 12 x 1024 float32, views cut here (~0.8 s)
  bank = Bank.open()                                   # train + val, ~0.4 GB of RAM, ~2 s
  candidates = bank.search(emb, k=20, view_names=names)
  head = RegionHead.load()
  head.predict(emb, top=4)                             # [(region, country, prob)]
  candidates += head.candidates(emb, k=4)              # role="area", one per region

Every call depends only on its arguments and the read-only bank: no state carries across panoramas.
"""
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from panoloc.candidates import Candidate

REPO_ROOT = Path(__file__).resolve().parent.parent
OSV_DIR = REPO_ROOT / "Data" / "osv5m"
EMB_DIR = OSV_DIR / "emb"
PARTITIONS_CSV = OSV_DIR / "partitions.csv"

MODEL_ID = "hf-hub:timm/PE-Core-L-14-336"
EMBED_DIM = 1024
EMBED_VERSION = "pecore-l14-336.vision.squash336.fp16.v1"
PREPROCESS = {"resize": [336, 336], "resize_mode": "squash", "interpolation": "bilinear", "antialias": True,
              "mean": [0.5, 0.5, 0.5], "std": [0.5, 0.5, 0.5], "input": "RGB uint8 via PIL"}

GALLERY_PARTITIONS = ("train", "val")
RESERVED_PARTITIONS = ("test",)  # the final external test: never in a gallery
VIEW_CROP = "4:3"
VIEW_SIZE = 512  # cutting at 512 px is enough for a 336 px input
VIEW_FOV = 60.0
N_VIEWS = 12
PER_VIEW_K = 100
DEFAULT_K = 20
TAU = 0.05
SOURCE = "osv5m"
GROUP = "pe-core"
NOTE = "scene resemblance to an OSV-5M photo, not a verified match"


# -- model ----------------------------------------------------------------------------------------

class PECore:
    """PE-Core-L/14-336 vision tower, loaded once. embed() returns float32 L2-normalised rows."""

    def __init__(self, device=None, dtype="float16", threads=4):
        import open_clip
        import torch
        torch.set_num_threads(threads)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.dtype = getattr(torch, dtype) if self.device != "cpu" else torch.float32
        model, _, preprocess = open_clip.create_model_and_transforms(MODEL_ID)
        self.visual = model.visual.to(device=self.device, dtype=self.dtype).eval()
        del model  # the text tower is never needed
        self.preprocess = preprocess  # PIL image -> 3 x 336 x 336 float tensor, exactly PREPROCESS
        self._torch = torch

    def embed_tensor(self, batch):
        """A preprocessed N x 3 x 336 x 336 batch -> N x 1024 normalised float32 torch tensor on the CPU."""
        torch = self._torch
        with torch.inference_mode():
            out = self.visual(batch.to(self.device, self.dtype, non_blocking=True)).float()
            return torch.nn.functional.normalize(out, dim=-1).cpu()

    def embed(self, images, batch_size=16):
        """PIL images (or H x W x 3 uint8 arrays) -> N x 1024 float32, L2-normalised."""
        rows = []
        for i in range(0, len(images), batch_size):
            chunk = [im if isinstance(im, Image.Image) else Image.fromarray(np.asarray(im)) for im in images[i:i + batch_size]]
            batch = self._torch.stack([self.preprocess(im.convert("RGB")) for im in chunk])
            rows.append(self.embed_tensor(batch).numpy())
        return np.concatenate(rows) if rows else np.zeros((0, EMBED_DIM), np.float32)


def view_image(view, crop=VIEW_CROP):
    """The part of a panoloc.views View (or a square H x W x 3 array) that is embedded, as a PIL image."""
    img = np.asarray(getattr(view, "image", view))
    if crop == "4:3":
        h = img.shape[0]
        img = img[h // 8: h - h // 8]
    elif crop != "square":
        raise ValueError(f"crop must be '4:3' or 'square', got {crop!r}")
    return Image.fromarray(img)


def embed_views(model, pano_or_views, crop=VIEW_CROP, size=VIEW_SIZE, fov_deg=VIEW_FOV, n_views=N_VIEWS):
    """Embed a panorama's horizontal views -> (V x 1024 float32, view names).

    pano_or_views: an equirectangular H x W x 3 array (load_panorama), cut here into n_views views of
    fov_deg and `size` px (the measured default), or a View list of cut_views, whose horizontal views
    (h...) are used as they are: views cut at other settings (the pipeline's 8 x 90 degrees) work, but
    scored lower on validation.
    """
    if isinstance(pano_or_views, np.ndarray):
        from panoloc.views import cut_views
        pano_or_views = cut_views(pano_or_views, size=size, fov_deg=fov_deg, n_horizontal=n_views)
    views = [v for v in pano_or_views if v.name.startswith("h")]
    if not views:
        raise ValueError("no horizontal views (h000, h030, ...) to embed")
    return model.embed([view_image(v, crop) for v in views]), [v.name for v in views]


# -- bank -----------------------------------------------------------------------------------------

def read_manifest(emb_dir=EMB_DIR):
    return json.loads((Path(emb_dir) / "manifest.json").read_text())


def read_partitions(path=PARTITIONS_CSV):
    import pandas as pd
    return pd.read_csv(path, dtype={"id": str, "group": str, "region": str}, keep_default_na=False)


def load_embeddings(partitions=GALLERY_PARTITIONS, emb_dir=EMB_DIR, partitions_csv=PARTITIONS_CSV, dtype=np.float16):
    """(metadata DataFrame, N x 1024 embeddings) of the given partitions, in shard order, unreadable images left out.

    Streams the shards: peak memory is the selected rows plus one shard.
    """
    emb_dir = Path(emb_dir)
    man = read_manifest(emb_dir)
    if man.get("version") != EMBED_VERSION:
        raise ValueError(f"bank embeddings are {man.get('version')!r}, this code embeds {EMBED_VERSION!r}")
    meta = read_partitions(partitions_csv).set_index("id")
    keep_parts = set(partitions)
    ids, chunks = [], []
    for k in range(man["n_shards"]):
        with np.load(emb_dir / f"shard_{k:05d}.npz") as z:
            sid = z["ids"].astype(str)
            sel = z["ok"] & np.isin(meta.loc[sid, "partition"].to_numpy(), list(keep_parts))
            ids.extend(sid[sel].tolist())
            chunks.append(z["emb"][sel].astype(dtype))
    emb = np.concatenate(chunks) if chunks else np.zeros((0, EMBED_DIM), dtype)
    return meta.loc[ids].reset_index(), emb


@dataclass(eq=False)
class Bank:
    """A read-only faiss IndexFlatIP over the bank embeddings of some partitions, with their metadata."""
    index: object
    ids: np.ndarray
    lat: np.ndarray
    lon: np.ndarray
    country: np.ndarray
    region: np.ndarray
    ref_group: np.ndarray
    partition: np.ndarray
    partitions: tuple

    @classmethod
    def open(cls, partitions=GALLERY_PARTITIONS, emb_dir=EMB_DIR, partitions_csv=PARTITIONS_CSV, threads=4):
        """Load the shards of `partitions` into faiss (inner product = cosine on normalised rows)."""
        partitions = tuple(partitions)
        if set(partitions) & set(RESERVED_PARTITIONS):
            raise ValueError(f"{RESERVED_PARTITIONS} is the final external test: never a gallery")
        import faiss
        faiss.omp_set_num_threads(threads)
        meta, emb = load_embeddings(partitions, emb_dir, partitions_csv, dtype=np.float16)
        index = faiss.IndexFlatIP(EMBED_DIM)
        for i in range(0, len(emb), 8192):
            index.add(np.ascontiguousarray(emb[i:i + 8192], dtype=np.float32))
        return cls.from_arrays(index, meta, partitions)

    @classmethod
    def from_arrays(cls, index, meta, partitions=GALLERY_PARTITIONS):
        """A Bank over an index whose row i is meta row i (meta: id, lat, lon, country, region, group, partition)."""
        col = lambda c: meta[c].to_numpy() if hasattr(meta, "to_numpy") else np.asarray(meta[c])  # noqa: E731
        return cls(index, col("id").astype(str), col("lat").astype(float), col("lon").astype(float),
                   col("country").astype(str), col("region").astype(str), col("group").astype(str),
                   col("partition").astype(str), tuple(partitions))

    def __len__(self):
        return len(self.ids)

    def neighbours(self, view_embeddings, per_view_k=PER_VIEW_K):
        """Raw per-view hits: (V x K similarities, V x K bank rows; -1 where fewer than K exist)."""
        q = np.ascontiguousarray(np.atleast_2d(view_embeddings), dtype=np.float32)
        return self.index.search(q, min(per_view_k, len(self)))

    def search(self, view_embeddings, k=DEFAULT_K, per_view_k=PER_VIEW_K, tau=TAU, view_names=None, dedup="group"):
        """Candidates from the views of ONE panorama (or one photo): see the module docstring."""
        sims, rows = self.neighbours(view_embeddings, per_view_k)
        return aggregate(sims, rows, self, k=k, tau=tau, view_names=view_names, dedup=dedup)


def aggregate(sims, rows, bank, k=DEFAULT_K, tau=TAU, view_names=None, dedup="group"):
    """Merge per-view neighbours into weighted group candidates (module docstring, steps 1-3).

    sims, rows: V x K arrays of similarities and bank rows (-1 = no neighbour). bank: anything with
    ids, lat, lon, country, region, ref_group and partition arrays indexed by row. dedup="image"
    skips step 1's merging (every bank image is its own group): for evaluation only.
    """
    if dedup not in ("group", "image"):
        raise ValueError(f"dedup must be 'group' or 'image', got {dedup!r}")
    sims, rows = np.atleast_2d(sims), np.atleast_2d(rows)
    n_views = len(rows)
    names = list(view_names) if view_names is not None else [f"v{i}" for i in range(n_views)]
    if len(names) != n_views:
        raise ValueError("one view name per row of view embeddings")
    if not tau > 0:
        raise ValueError(f"tau must be > 0, got {tau}")
    weight, best, views, images, sim_sum = {}, {}, {}, {}, {}
    for v in range(n_views):
        per_group = {}  # group -> (best similarity in this view, its row)
        for s, r in zip(sims[v], rows[v]):
            if r < 0 or not math.isfinite(s):
                continue
            g = bank.ref_group[r] if dedup == "group" else f"{bank.ref_group[r]}#{r}"
            images.setdefault(g, set()).add(int(r))
            if g not in per_group or s > per_group[g][0]:
                per_group[g] = (float(s), int(r))
        if not per_group:
            continue
        top = max(s for s, _ in per_group.values())
        kern = {g: math.exp((s - top) / tau) for g, (s, _) in per_group.items()}
        total = sum(kern.values())
        for g, (s, r) in per_group.items():
            weight[g] = weight.get(g, 0.0) + kern[g] / total / n_views
            views.setdefault(g, []).append(names[v])
            sim_sum[g] = sim_sum.get(g, 0.0) + s
            if g not in best or s > best[g][0]:
                best[g] = (s, r)
    ranked = sorted(weight, key=lambda g: (-weight[g], -best[g][0], g))[:k]
    out = []
    for rank, g in enumerate(ranked, start=1):
        s, r = best[g]
        out.append(Candidate(
            float(bank.lat[r]), float(bank.lon[r]), "camera", f"{SOURCE}:{bank.ids[r]}",
            label=f"OSV-5M photo {bank.ids[r]} ({bank.region[r]}, {bank.country[r]})",
            weight=weight[g], accuracy_m=None, extent_m=None, country=str(bank.country[r]), group=GROUP,
            details={"similarity": round(s, 4), "mean_similarity": round(sim_sum[g] / len(views[g]), 4),
                     "views": views[g], "n_views": len(views[g]), "n_images": len(images[g]),
                     "ref_group": str(bank.ref_group[r]), "group_kind": "sequence" if g.startswith("seq:") else "block",
                     "region": str(bank.region[r]), "partition": str(bank.partition[r]), "rank": rank,
                     "tau": tau, "note": NOTE}))
    return out


# -- mini-PIGEON region head (PLAN.md 4.2, TASKS.md T37) ------------------------------------------

HEAD_DIR = OSV_DIR / "head"
HEAD_SOURCE = "regionhead"


@dataclass(eq=False)
class RegionHead:
    """Linear head on frozen PE-Core embeddings: PT districts (+ Madeira, Azores), ES communities, FR regions.

    tools/train_region_head.py trains it on the `train` partition with class weights, early-stops and
    fits one temperature on `val`, and saves Data/osv5m/head/ (head.npz, classes.json, train_ids.txt.gz,
    report.json). Runtime is numpy only. Classes are "<country>:<region>" with OSV-5M's region names
    (France: the 22 regions before 2016). The Canary Islands, Ceuta and Melilla have no class.

    probs() gives calibrated per-row probabilities; predict() averages them over the rows (the views
    of one panorama: an average, not a product, PLAN.md 3.2). The class weights flatten the sample
    counts, so the implied prior is far from the OSV-5M collection density, and far from uniform over
    area too: fusion should not read it as a geographic prior.

    candidates() gives one `area` Candidate per top region. Its point is the region's training image
    with the highest mean non-urban theta to all of that region's training images (the PLAN.md 1.1
    optimum under the region's image density, not its plain centroid), and extent_m is the 80th
    percentile distance from that point to the region's images. Both come from classes.json.
    """
    W: np.ndarray  # C x D
    b: np.ndarray  # C
    temperature: float
    classes: list  # dicts: name, country, region, n_train, lat, lon, extent_m

    @classmethod
    def load(cls, head_dir=HEAD_DIR):
        head_dir = Path(head_dir)
        z = np.load(head_dir / "head.npz")
        classes = json.loads((head_dir / "classes.json").read_text())["classes"]
        if str(z["embed_version"]) != EMBED_VERSION:
            raise ValueError(f"head trained on {z['embed_version']}, this code embeds {EMBED_VERSION}")
        return cls(z["W"].astype(np.float32), z["b"].astype(np.float32), float(z["temperature"]), classes)

    def probs(self, embeddings):
        """N x D embeddings -> N x C calibrated probabilities."""
        logits = (np.atleast_2d(embeddings).astype(np.float32) @ self.W.T + self.b) / self.temperature
        logits -= logits.max(axis=1, keepdims=True)
        p = np.exp(logits)
        return p / p.sum(axis=1, keepdims=True)

    def predict(self, embeddings, top=None):
        """[(region, country, prob)] for the rows averaged, most likely first; all classes unless top."""
        p = self.probs(embeddings).mean(axis=0)
        order = np.argsort(-p)[:top]
        return [(self.classes[i]["region"], self.classes[i]["country"], float(p[i])) for i in order]

    def candidates(self, embeddings, k=4):
        """One `area` Candidate per top-k region, weight = its averaged probability."""
        p = self.probs(embeddings).mean(axis=0)
        out = []
        for rank, i in enumerate(np.argsort(-p)[:k], start=1):
            c = self.classes[i]
            out.append(Candidate(
                c["lat"], c["lon"], "area", f"{HEAD_SOURCE}:{c['name']}", label=f"{c['region']} ({c['country']})",
                weight=float(p[i]), accuracy_m=None, extent_m=c["extent_m"], country=c["country"], group=GROUP,
                details={"prob": round(float(p[i]), 4), "region": c["region"], "class": c["name"], "rank": rank,
                         "n_views": len(np.atleast_2d(embeddings)), "n_train": c["n_train"],
                         "point_method": "training image with the highest mean non-urban theta to its region's images",
                         "extent_source": "80th percentile distance of the region's training images",
                         "note": "regional prior from scene appearance, not a camera position"}))
        return out


def main(argv=None):
    """CLI smoke test: python -m panoloc.retrieval <panorama.jpg> [--k 10] -> candidates and timings."""
    import argparse
    import os
    import time
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from panoloc.views import load_panorama
    ap = argparse.ArgumentParser(description="PE-Core kNN + region head on one panorama")
    ap.add_argument("panorama")
    ap.add_argument("--k", type=int, default=10)
    args = ap.parse_args(argv)
    t = {}
    t0 = time.time()
    model, bank = PECore(), Bank.open()
    head = RegionHead.load() if (HEAD_DIR / "head.npz").exists() else None
    t["load_s"] = time.time() - t0
    t0 = time.time()
    pano = load_panorama(args.panorama)
    t["load_panorama_s"] = time.time() - t0
    t0 = time.time()
    emb, names = embed_views(model, pano)
    t["cut_and_embed_s"] = time.time() - t0
    t0 = time.time()
    cands = bank.search(emb, k=args.k, view_names=names)
    t["search_s"] = time.time() - t0
    for c in cands:
        print(f"{c.weight:.3f}  {c.lat:.5f},{c.lng:.5f}  {c.details['similarity']:.3f}  {c.details['n_views']} views  {c.label}")
    if head:
        for c in head.candidates(emb, k=4):
            print(f"{c.weight:.3f}  {c.lat:.5f},{c.lng:.5f}  extent {c.extent_m / 1000:.0f} km  {c.label}")
    print({k: round(v, 2) for k, v in t.items()})


if __name__ == "__main__":
    main()
