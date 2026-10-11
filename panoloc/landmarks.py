"""Commons landmark gallery: PE-Core retrieval of Wikidata landmark photos (PLAN.md 3.2, 3.3, 4.5; TASKS.md T33).

The gallery holds the Wikimedia Commons photo (P18, 500 px) of Wikidata items in Portugal, Spain and
France, fetched by tools/fetch_commons.py into Data/gallery/commons/<CC>/<QID>.jpg and embedded by
tools/embed_gallery.py into Data/gallery/emb/ (shards + manifest, see that script) with
panoloc.retrieval.PECore: the model and preprocessing of the OSV-5M bank and of the panorama views.

What a hit means. A gallery coordinate is the item's Wikidata P625: the landmark, or the centre of
the place, never a camera. The camera of the panorama, like the photographer of the Commons photo,
can stand 50-500 m from that point (CAMERA_OFFSET_M, an assumption: a façade seen across a square, a
bridge from the bank, a castle from the town below), and further for large objects. A visual
neighbour is resemblance, not identity: another church of the same style, another Manueline portal,
another beach. So every hit is a `landmark` candidate with details["verified_match"] = False. Only a
geometric check (panoloc.verify, T41) may set it to True, and a verified landmark still marks the
landmark, not the camera.

Search (Gallery.search), aggregated like panoloc.retrieval.Bank.search:
  0. Score: score = cos(view, photo) - beta x hub(photo). hub is the photo's mean cosine to its 10
     nearest OSV-5M train photos (tools/embed_gallery.py): a generic street or village photo that
     resembles every road scene is pushed down (CSLS hubness correction). The index holds
     [embedding, hub] and the query [embedding, -beta], so the search over this score is exact.
     beta = HUB_BETA (1.0) gave the best top-1 on Panoramax val (Data/gallery/emb/eval_landmarks.json:
     PT top-1 within 100 m 13.7% against 6.9% without the correction).
  1. Per view, the PER_VIEW_K photos with the highest score. Within a view a QID keeps its best
     photo: s_vq.
  2. Per view, kernel weights over its QIDs: p_vq = exp((s_vq - s_v,max) / tau) / sum_q' exp(...).
     Each view casts one vote.
  3. weight_q = (1/V) sum_v p_vq: the average over all V views, never a product (PLAN.md 3.2). A QID
     seen in several views counts once, with its views listed; a view that did not retrieve it adds 0.
  4. Gate: a QID whose best cosine over the views is below min_similarity (MIN_SIMILARITY, 0.70) is
     left out, and its weight is not passed on to the others.
Before the gate the weights of all retrieved QIDs sum to 1; weight is the QID's share of the
panorama's landmark-retrieval support, not a calibrated probability, and the sum of what passes the
gate says how much of that support resembles a gallery photo closely. Without the gate every
panorama gets neighbours, landmark or not, and photos the hub correction favours despite a low cosine
(artworks, interiors) can rank first. On Panoramax val (gallery: Portugal only, 15 k photos; 12
views of 60 degrees) the top-1 lies within 1 km of the camera for 14 of 73 PT panoramas with the
gate (6 without it), and candidates remain for 96% of PT panoramas and 47% of ES/FR ones, which can
only get Portuguese landmarks today. Weigh what passes by similarity and verification, not by
weight alone.

Each QID becomes one Candidate:
  role="landmark", source="commons:<qid>", group="pe-core" (the encoder of the bank kNN and the region
  head: fusion caps their combined influence, PLAN.md 3.2), weight as above, accuracy_m=None
  (Wikidata states no accuracy), extent_m = the name index's assumed radius for the item's P31
  types (tools/build_name_index.py WikidataRoles, applied by tools/embed_gallery.py), country,
  details: similarity (best cosine over the views), score (best hub-corrected score), mean_similarity
  (over the views that retrieved it), hub, views, n_views, qid, name, types, type_labels, type_role
  (`area` for a town, parish or park), heritage, sitelinks, commons_file, commons_page, photo (path
  under Data/gallery/commons/), extent_source ("assumed"), extent_rule, camera_offset_m,
  verified_match (False), rank, tau, beta, min_similarity, note.
The same item can also come from the name index as "wikidata:<qid>": details["qid"] links the two.

  from panoloc.retrieval import PECore, embed_views
  from panoloc.landmarks import Gallery
  emb, names = embed_views(PECore(), pano)         # the bank search's view embeddings (12 views of 60 degrees)
  gallery = Gallery.open()                         # Data/gallery/emb: ~5 KB of RAM per photo, ~1 s per 10 k
  candidates = gallery.search(emb, k=10, view_names=names)
  gallery.photo_path(candidates[0])                # the Commons photo, for panoloc.verify

Every call depends only on its arguments and the read-only gallery: nothing carries across panoramas.
"""
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from panoloc.candidates import Candidate
from panoloc.retrieval import EMBED_DIM, EMBED_VERSION

REPO_ROOT = Path(__file__).resolve().parent.parent
GALLERY_DIR = REPO_ROOT / "Data" / "gallery"
COMMONS_DIR = GALLERY_DIR / "commons"
EMB_DIR = GALLERY_DIR / "emb"
SHARD_GLOB = "shard_[0-9][0-9][0-9][0-9][0-9].npz"

PER_VIEW_K = 50
DEFAULT_K = 10
TAU = 0.05
HUB_BETA = 1.0
MIN_SIMILARITY = 0.70  # gate on a candidate's best cosine (step 4), calibrated on Panoramax val
CAMERA_OFFSET_M = (50, 500)  # assumed distance from a landmark point to a camera that shows it
SOURCE = "commons"
GROUP = "pe-core"
NOTE = ("visual resemblance to the Commons photo of a Wikidata item, not identity; the point is the "
        "landmark's, and the camera can stand 50-500 m from it")
META_TEXT = ("key", "qid", "country", "name", "types", "type_labels", "heritage", "commons_file",
             "commons_page", "other_qids", "photo", "type_role", "extent_rule")
META_NUM = ("lat", "lon", "sitelinks", "extent_m", "hub")


def _split(s):
    return [x for x in str(s).split("|") if x]


def _index(emb, hub, threads=4):
    """faiss IndexFlatIP over [embedding, hub] rows: <[q, -beta], [g, hub]> = cos(q, g) - beta x hub."""
    import faiss
    faiss.omp_set_num_threads(threads)
    index = faiss.IndexFlatIP(EMBED_DIM + 1)
    for i in range(0, len(emb), 8192):
        rows = np.ascontiguousarray(np.c_[np.asarray(emb[i:i + 8192], np.float32), np.asarray(hub[i:i + 8192], np.float32)])
        index.add(rows)
    return index


@dataclass(eq=False)
class Gallery:
    """A read-only faiss index over the gallery photos, with one metadata array per field (row i = photo i)."""
    index: object
    meta: dict

    @classmethod
    def open(cls, emb_dir=EMB_DIR, countries=None, threads=4):
        """Load every shard of `emb_dir` (only `countries`, if given). A shard written before its hub column
        (an interrupted tools/embed_gallery.py run) gets the gallery's median hub."""
        emb_dir = Path(emb_dir)
        paths = sorted(emb_dir.glob(SHARD_GLOB))
        if not paths:
            raise FileNotFoundError(f"no gallery shards in {emb_dir}: run tools/embed_gallery.py")
        cols, embs = {c: [] for c in META_TEXT + META_NUM}, []
        for p in paths:
            with np.load(p) as z:
                if str(z["version"]) != EMBED_VERSION:
                    raise ValueError(f"{p.name} holds {z['version']} embeddings, this code embeds {EMBED_VERSION}")
                sel = np.isin(z["country"], list(countries)) if countries else np.ones(len(z["key"]), bool)
                for c in cols:
                    cols[c].append(z[c][sel] if c in z.files else np.full(int(sel.sum()), np.nan, np.float32))
                embs.append(z["emb"][sel])
        meta = {c: np.concatenate(v) for c, v in cols.items()}
        for c in META_TEXT:  # fixed-width unicode costs the longest value on every row
            meta[c] = meta[c].astype(object)
        hub = meta["hub"].astype(np.float32)
        if np.isnan(hub).any():
            hub[np.isnan(hub)] = np.nanmedian(hub) if (~np.isnan(hub)).any() else 0.0
        meta["hub"] = hub
        return cls(_index(np.concatenate(embs), hub, threads), meta)

    @classmethod
    def from_arrays(cls, emb, meta):
        """A Gallery over N x 1024 embeddings and metadata (field -> sequence of N) with at least qid, lat,
        lon and extent_m; other fields default to empty strings or 0, hub included (tests, small galleries)."""
        n = len(meta["qid"])
        full = {c: np.asarray(meta[c]) if c in meta else np.array([""] * n) for c in META_TEXT}
        full.update({c: np.asarray(meta[c], dtype=float) if c in meta else np.zeros(n) for c in META_NUM})
        if "key" not in meta:
            full["key"] = np.array([f"{c}/{q}" for c, q in zip(full["country"], full["qid"])])
        return cls(_index(np.asarray(emb, np.float32).reshape(n, EMBED_DIM), full["hub"]), full)

    def __len__(self):
        return len(self.meta["qid"])

    def countries(self):
        cc, n = np.unique(self.meta["country"], return_counts=True)
        return {str(c): int(k) for c, k in zip(cc, n)}

    def row_of(self, qid):
        hits = np.flatnonzero(self.meta["qid"] == qid)
        return int(hits[0]) if len(hits) else None

    def photo_path(self, candidate_or_row, commons_dir=COMMONS_DIR):
        """Path of the Commons photo of a gallery row, or of a Candidate from search() (None if unknown)."""
        if isinstance(candidate_or_row, (int, np.integer)):
            row = int(candidate_or_row)
        else:
            row = self.row_of(candidate_or_row.details.get("qid"))
            if row is None:
                return None
        return Path(commons_dir) / str(self.meta["photo"][row])

    def neighbours(self, view_embeddings, per_view_k=PER_VIEW_K, beta=HUB_BETA):
        """Raw per-view hits: (V x K scores, V x K cosine similarities, V x K rows; -1 where fewer than K exist)."""
        q = np.atleast_2d(np.asarray(view_embeddings, np.float32))
        q = np.ascontiguousarray(np.c_[q, np.full(len(q), -beta, np.float32)])
        scores, rows = self.index.search(q, min(per_view_k, len(self)))
        sims = scores + beta * np.where(rows >= 0, self.meta["hub"][np.maximum(rows, 0)], 0.0)
        return scores, sims, rows

    def search(self, view_embeddings, k=DEFAULT_K, per_view_k=PER_VIEW_K, tau=TAU, beta=HUB_BETA,
               min_similarity=MIN_SIMILARITY, view_names=None):
        """Landmark candidates from the views of ONE panorama (or one photo): see the module docstring."""
        scores, sims, rows = self.neighbours(view_embeddings, per_view_k, beta)
        return aggregate(scores, rows, self.meta, k=k, tau=tau, min_similarity=min_similarity,
                         view_names=view_names, similarities=sims, beta=beta)


def aggregate(scores, rows, meta, k=DEFAULT_K, tau=TAU, min_similarity=MIN_SIMILARITY, view_names=None,
              similarities=None, beta=0.0):
    """Merge per-view neighbours into weighted landmark candidates (module docstring, steps 1-3).

    scores, rows: V x K arrays of ranking scores and gallery rows (-1 = no neighbour). similarities:
    the V x K cosine similarities behind the scores (the scores themselves when None, i.e. no hub
    correction). meta: field -> array indexed by row (Gallery.meta), at least qid, lat, lon, extent_m.
    """
    scores, rows = np.atleast_2d(scores), np.atleast_2d(rows)
    sims = scores if similarities is None else np.atleast_2d(similarities)
    n_views = len(rows)
    names = list(view_names) if view_names is not None else [f"v{i}" for i in range(n_views)]
    if len(names) != n_views:
        raise ValueError("one view name per row of view embeddings")
    if not tau > 0:
        raise ValueError(f"tau must be > 0, got {tau}")
    get = lambda c, r, default="": meta[c][r] if c in meta else default  # noqa: E731
    weight, best, best_sim, views, sim_sum = {}, {}, {}, {}, {}
    for v in range(n_views):
        per_qid = {}  # qid -> (best score in this view, its cosine, its row)
        for s, c, r in zip(scores[v], sims[v], rows[v]):
            if r < 0 or not (math.isfinite(s) and math.isfinite(c)):
                continue
            q = str(meta["qid"][r])
            if q not in per_qid or s > per_qid[q][0]:
                per_qid[q] = (float(s), float(c), int(r))
        if not per_qid:
            continue
        top = max(s for s, _, _ in per_qid.values())
        kern = {q: math.exp((s - top) / tau) for q, (s, _, _) in per_qid.items()}
        total = sum(kern.values())
        for q, (s, c, r) in per_qid.items():
            weight[q] = weight.get(q, 0.0) + kern[q] / total / n_views
            views.setdefault(q, []).append(names[v])
            sim_sum[q] = sim_sum.get(q, 0.0) + c
            best_sim[q] = max(best_sim.get(q, -math.inf), c)
            if q not in best or s > best[q][0]:
                best[q] = (s, r)
    passed = [q for q in weight if best_sim[q] >= min_similarity]
    ranked = sorted(passed, key=lambda q: (-weight[q], -best[q][0], q))[:k]
    out = []
    for rank, q in enumerate(ranked, start=1):
        s, r = best[q]
        name, country = str(get("name", r)), str(get("country", r)) or None
        type_labels = _split(get("type_labels", r))
        label = f"{name or q} ({type_labels[0]})" if type_labels else (name or q)
        out.append(Candidate(
            float(meta["lat"][r]), float(meta["lon"][r]), "landmark", f"{SOURCE}:{q}",
            label=f"Commons photo of {label}", weight=weight[q], accuracy_m=None,
            extent_m=float(meta["extent_m"][r]), country=country, group=GROUP,
            details={"similarity": round(best_sim[q], 4), "score": round(s, 4),
                     "mean_similarity": round(sim_sum[q] / len(views[q]), 4), "hub": round(float(get("hub", r, 0.0)), 4),
                     "views": views[q], "n_views": len(views[q]), "qid": q, "name": name,
                     "types": _split(get("types", r)), "type_labels": type_labels,
                     "type_role": str(get("type_role", r)) or None, "heritage": _split(get("heritage", r)),
                     "sitelinks": int(get("sitelinks", r, 0)), "commons_file": str(get("commons_file", r)),
                     "commons_page": str(get("commons_page", r)), "photo": str(get("photo", r)),
                     "extent_source": "assumed", "extent_rule": str(get("extent_rule", r)),
                     "camera_offset_m": list(CAMERA_OFFSET_M), "verified_match": False, "rank": rank,
                     "tau": tau, "beta": beta, "min_similarity": min_similarity, "note": NOTE}))
    return out


def read_manifest(emb_dir=EMB_DIR):
    return json.loads((Path(emb_dir) / "manifest.json").read_text())
