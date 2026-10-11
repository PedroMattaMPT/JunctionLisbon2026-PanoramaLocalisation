"""Geometric verification of reference photos: MegaLoc re-ranking + ALIKED/LightGlue + RANSAC (PLAN.md 3.3; TASKS.md T41).

Checks whether the views of ONE panorama show what a reference photo shows: the Commons photo of a
landmark candidate (panoloc.landmarks), or any other photo with a path (an OSV-5M bank image).
  1. Optional, Verifier(megaloc=True): MegaLoc (gmberton/MegaLoc, loaded offline from the torch hub
     cache, HF_HUB_OFFLINE=1), one 8448-d L2-normalised descriptor per image (ImageNet normalisation,
     322 x 322 resize, as in its README). The cosine between a view and a reference picks the
     views_per_candidate views worth matching. Off by default: on the calibration pairs its cosine
     separates poorly (far false pairs reach 0.23, above the median 0.13 of true ones), its top 3
     views find 9 of the 11 verifiable pairs and its top 6 all 11, while matching all 8 views needs
     no extra ~1 GB of GPU memory.
  2. ALIKED (aliked-n16, at most MAX_KEYPOINTS keypoints) + LightGlue match a view (long side
     MATCH_SIZE) against the reference photo, once per PHOTO_SCALES long side: 1024 suits a landmark
     that fills the view, 400 one seen small from 200 m (a façade 40 px tall in the view); the best
     scale is kept. Only matches with LightGlue confidence >= MIN_SCORE go into a fundamental-matrix
     RANSAC (OpenCV USAC_MAGSAC, RANSAC_PX px), which keeps those consistent with one rigid scene:
     inliers = their count. On all matches, low-confidence ones included, RANSAC finds 15-100
     "inliers" between unrelated photos lined up along a horizon or tree line, a degenerate set any
     fundamental matrix fits (raw_inliers, a diagnostic). spread (share of a 4 x 4 grid over the view
     holding an inlier) and thickness (minor-axis standard deviation of the inliers / the view's side)
     are diagnostics too: a true landmark often fills a thin band of the view, so neither separates.
A pair is verified when inliers >= MIN_INLIERS (21). Calibration (tools/eval_verify.py, Data/gallery/
emb/eval_verify.json): Panoramax val views against Commons photos of landmarks within 300 m, labelled
by eye as visible (48 pairs) or not (296), plus 212 top PE-Core neighbours more than 5 km away. At 21
no false pair passes (0 of 508, so a false rate per pair below ~0.6% at 95%) and 11 of the 48 visible
landmarks do: the prominent ones (a pavilion 30 m away, a bridge, a fountain, a monastery across the
river, a museum wing 150 m away at the 400 px scale). 10 of the 15 panoramas that show a gallery
landmark get one verified; none gets a false one. Most distant or partly hidden landmarks fail, so a
failed check is weak evidence of absence. The closest false pairs (15-20 inliers) are houses of the
same regional style (white walls, yellow trim) and a generic façade; at 18 inliers recall rises to
16/48 with 2 false pairs. The threshold was chosen on these same pairs: treat it as calibrated, not
as independently tested.

What a verified match means. The panorama and the reference show the same object or scene, not the
same viewpoint. A verified Commons photo still marks the landmark (Wikidata P625), never the camera:
the candidate stays role="landmark". A verified OSV-5M or Panoramax photo is an approximate camera
anchor: the reference camera may stand across the square, and its GPS has its own error, so it is
never a sub-10 m fix (PLAN.md 3.3). Repeated façades, chain-store fronts and shared building styles
can still produce inliers: the threshold limits that, it does not exclude it.

  from panoloc.verify import Verifier
  ver = Verifier()                                  # ALIKED + LightGlue: ~2 s to load, < 2.5 GB peak GPU
  checked = ver.verify(views, candidates, gallery.photo_path, top=10)   # ~0.5 s per candidate, all 8 views
  # copies of the candidates with details: verified_match, inliers, matches, confident, thickness,
  # spread, verify_view, megaloc_similarity, verify_ms; in the given order. Unverified ones keep
  # verified_match = False.
  m = ver.match_images(view_image, photo)          # one pair: Match(matches, confident, inliers, ...)
  ver.close()                                       # free the GPU memory

Every call depends only on its arguments: nothing carries across panoramas.
"""
import os
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np

MEGALOC_HUB = Path(os.path.expanduser("~/.cache/torch/hub/gmberton_MegaLoc_main"))
MEGALOC_SIZE = 322
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
MAX_KEYPOINTS = 2048
MATCH_SIZE = 1024
PHOTO_SCALES = (1024, 400)  # long sides the reference photo is matched at
RANSAC_PX = 2.0
MIN_SCORE = 0.5  # LightGlue match confidence for a match to enter RANSAC
MIN_MATCHES = 8  # a fundamental matrix needs 8 correspondences
GRID = 4
MIN_INLIERS = 21  # calibrated: no false pair of 508 at or above it (module docstring)
MIN_THICKNESS = 0.0  # diagnostic only
VIEWS_PER_CANDIDATE = 6  # with MegaLoc: the views of highest similarity that are matched (6 kept all 11 hits)


@dataclass
class Match:
    matches: int  # LightGlue matches
    confident: int  # those with confidence >= MIN_SCORE
    inliers: int  # RANSAC inliers among the confident matches
    raw_inliers: int  # RANSAC inliers among all matches (diagnostic: degenerate sets inflate it)
    spread: float  # share of the GRID x GRID cells of image 0 holding an inlier
    thickness: float  # minor-axis std of the inliers in image 0 / its longer side (0 for a line)
    ms: float  # matching + RANSAC time (match_images: extraction included)
    view: str | None = None
    scale: int | None = None  # long side the reference photo was matched at

    @property
    def inlier_ratio(self):
        return self.inliers / self.confident if self.confident else 0.0

    def verified(self, min_inliers=MIN_INLIERS, min_thickness=MIN_THICKNESS):
        return self.inliers >= min_inliers and self.thickness >= min_thickness


def rgb_array(image):
    """A path, PIL image, View (with .image) or H x W x 3 array -> H x W x 3 uint8 RGB array."""
    from PIL import Image
    if isinstance(image, (str, Path)):
        with Image.open(image) as im:
            return np.asarray(im.convert("RGB"))
    image = getattr(image, "image", image)
    if isinstance(image, Image.Image):
        return np.asarray(image.convert("RGB"))
    arr = np.asarray(image)
    if arr.ndim == 2:
        arr = np.repeat(arr[..., None], 3, axis=2)
    if arr.ndim != 3 or arr.shape[2] != 3:
        raise ValueError(f"not an RGB image: shape {arr.shape}")
    return arr.astype(np.uint8, copy=False)


def grid_spread(points, width, height, grid=GRID):
    """Share of the grid x grid cells of a width x height image that hold at least one of the points."""
    pts = np.asarray(points, dtype=float).reshape(-1, 2)
    if not len(pts):
        return 0.0
    cx = np.clip((pts[:, 0] / width * grid).astype(int), 0, grid - 1)
    cy = np.clip((pts[:, 1] / height * grid).astype(int), 0, grid - 1)
    return len(set(zip(cx.tolist(), cy.tolist()))) / grid ** 2


def thickness(points, size):
    """Minor-axis standard deviation of the points / size: 0 for points on a line, ~0.29 for a full square."""
    pts = np.asarray(points, dtype=float).reshape(-1, 2)
    if len(pts) < 3:
        return 0.0
    return float(np.sqrt(max(np.linalg.eigvalsh(np.cov(pts.T))[0], 0.0)) / size)


def ransac_inliers(pts0, pts1, px=RANSAC_PX):
    """Boolean inlier mask of a fundamental-matrix MAGSAC fit; all False below MIN_MATCHES matches."""
    import cv2
    pts0, pts1 = np.asarray(pts0, np.float64).reshape(-1, 2), np.asarray(pts1, np.float64).reshape(-1, 2)
    none = np.zeros(len(pts0), bool)
    if len(pts0) < MIN_MATCHES:
        return none
    for method in (cv2.USAC_MAGSAC, cv2.FM_RANSAC):  # MAGSAC asserts on some degenerate sets
        try:
            _, mask = cv2.findFundamentalMat(pts0, pts1, method, px, 0.999, 10000)
        except cv2.error:
            continue
        return mask.ravel().astype(bool) if mask is not None and len(mask) == len(pts0) else none
    return none


class Verifier:
    """MegaLoc + ALIKED/LightGlue on one device, loaded once; see the module docstring."""

    def __init__(self, device=None, megaloc=False, max_keypoints=MAX_KEYPOINTS, match_size=MATCH_SIZE,
                 ransac_px=RANSAC_PX, min_score=MIN_SCORE, threads=4):
        import torch
        from lightglue import ALIKED, LightGlue
        torch.set_num_threads(threads)
        self.torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.match_size, self.ransac_px, self.min_score = match_size, ransac_px, min_score
        self.extractor = ALIKED(max_num_keypoints=max_keypoints).eval().to(self.device)
        self.matcher = LightGlue(features="aliked").eval().to(self.device)
        self.megaloc = None
        if megaloc:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            model = torch.hub.load(str(MEGALOC_HUB), "get_trained_model", source="local")
            self.megaloc = model.eval().to(self.device)

    def close(self):
        self.extractor = self.matcher = self.megaloc = None
        if self.device == "cuda":
            self.torch.cuda.empty_cache()

    # -- MegaLoc ----------------------------------------------------------------------------------

    def global_descriptors(self, images, batch_size=16):
        """Images -> N x 8448 float32 L2-normalised MegaLoc descriptors."""
        torch = self.torch
        if self.megaloc is None:
            raise RuntimeError("Verifier(megaloc=False) has no global descriptors")
        mean = torch.tensor(IMAGENET_MEAN, device=self.device).view(1, 3, 1, 1)
        std = torch.tensor(IMAGENET_STD, device=self.device).view(1, 3, 1, 1)
        out = []
        for i in range(0, len(images), batch_size):
            batch = []
            for im in images[i:i + batch_size]:
                x = torch.from_numpy(np.array(rgb_array(im))).to(self.device).permute(2, 0, 1)[None].float() / 255
                batch.append(torch.nn.functional.interpolate(x, size=(MEGALOC_SIZE, MEGALOC_SIZE), mode="bilinear",
                                                             antialias=True, align_corners=False))
            with torch.inference_mode():
                d = self.megaloc((torch.cat(batch) - mean) / std).float()
            out.append(torch.nn.functional.normalize(d, dim=-1).cpu().numpy())
        return np.concatenate(out) if out else np.zeros((0, 8448), np.float32)

    # -- local features ---------------------------------------------------------------------------

    def features(self, image, size=None):
        """ALIKED keypoints and descriptors of one image resized to `size` (MATCH_SIZE) on its long side,
        kept on the device, with the image's own size."""
        torch = self.torch
        arr = rgb_array(image)
        x = torch.from_numpy(np.array(arr)).to(self.device).permute(2, 0, 1).float() / 255  # a writable copy
        with torch.inference_mode():
            feats = self.extractor.extract(x, resize=size or self.match_size)
        feats["_wh"] = (arr.shape[1], arr.shape[0])
        return feats

    def match_features(self, f0, f1, view=None):
        """Match two feature sets -> Match (ms covers matching and RANSAC only)."""
        torch = self.torch
        t0 = time.perf_counter()
        with torch.inference_mode():
            out = self.matcher({"image0": {k: v for k, v in f0.items() if k != "_wh"},
                                "image1": {k: v for k, v in f1.items() if k != "_wh"}})
        idx = out["matches"][0].cpu().numpy()
        score = out["scores"][0].float().cpu().numpy()
        p0 = f0["keypoints"][0].cpu().numpy()[idx[:, 0]]
        p1 = f1["keypoints"][0].cpu().numpy()[idx[:, 1]]
        conf = score >= self.min_score
        mask = np.zeros(len(idx), bool)
        mask[conf] = ransac_inliers(p0[conf], p1[conf], self.ransac_px)
        raw = int(ransac_inliers(p0, p1, self.ransac_px).sum())
        w, h = f0["_wh"]
        return Match(int(len(idx)), int(conf.sum()), int(mask.sum()), raw, round(grid_spread(p0[mask], w, h), 4),
                     round(thickness(p0[mask], max(w, h)), 4), (time.perf_counter() - t0) * 1000, view)

    def match_images(self, image0, image1, view=None, scales=PHOTO_SCALES):
        """Extract and match one pair: image0 (the query view) at MATCH_SIZE, image1 (the reference) at
        each of `scales`; the Match with the most inliers. Spread and thickness are measured on image0."""
        t0 = time.perf_counter()
        f0 = self.features(image0)
        best = None
        for size in scales:
            m = replace(self.match_features(f0, self.features(image1, size), view), scale=size)
            if best is None or (m.inliers, m.confident) > (best.inliers, best.confident):
                best = m
        return replace(best, ms=(time.perf_counter() - t0) * 1000)

    # -- candidates -------------------------------------------------------------------------------

    def verify(self, views, candidates, photo_path, top=10, views_per_candidate=VIEWS_PER_CANDIDATE,
               min_inliers=MIN_INLIERS, min_thickness=MIN_THICKNESS, view_names=None, scales=PHOTO_SCALES):
        """Copies of `candidates` with verification details; only the first `top` are matched.

        views: the panorama's horizontal views (panoloc.views View objects or images). photo_path:
        candidate -> path of its reference photo (Gallery.photo_path for Commons hits), or None to
        skip it. Each checked candidate is matched against its views_per_candidate views of highest
        MegaLoc similarity (all views without MegaLoc), at every photo scale, keeping the best match.
        details gets verified_match, inliers, matches, confident, thickness, spread, verify_view,
        verify_scale, megaloc_similarity, verify_ms and verify_rule.
        """
        names = list(view_names) if view_names is not None else [getattr(v, "name", f"v{i}") for i, v in enumerate(views)]
        images = [rgb_array(v) for v in views]
        view_desc = self.global_descriptors(images) if self.megaloc is not None else None
        view_feats = {}
        out = []
        for rank, cand in enumerate(candidates):
            path = photo_path(cand) if rank < top else None
            if path is None or not Path(path).exists():
                out.append(cand)
                continue
            t0 = time.perf_counter()
            photo = rgb_array(path)
            if view_desc is not None:
                sim = view_desc @ self.global_descriptors([photo])[0]
                order = np.argsort(-sim)[:views_per_candidate]
            else:
                sim, order = None, range(len(images))
            refs = {size: self.features(photo, size) for size in scales}
            best = None
            for i in order:
                if i not in view_feats:
                    view_feats[i] = self.features(images[i])
                for size, ref in refs.items():
                    m = replace(self.match_features(view_feats[i], ref, names[i]), scale=size)
                    if best is None or (m.inliers, m.confident) > (best.inliers, best.confident):
                        best = m
            details = {**cand.details, "verified_match": bool(best.verified(min_inliers, min_thickness)),
                       "inliers": best.inliers, "matches": best.matches, "confident": best.confident,
                       "thickness": best.thickness, "spread": best.spread, "verify_view": best.view,
                       "verify_scale": best.scale,
                       "verify_ms": round((time.perf_counter() - t0) * 1000, 1),
                       "verify_rule": f"inliers >= {min_inliers} and thickness >= {min_thickness}"}
            if sim is not None:
                details["megaloc_similarity"] = round(float(sim.max()), 4)
            out.append(replace(cand, details=details))
        return out


def match_summary(m):
    """A Match as a plain dict (for logs and evaluation files)."""
    d = asdict(m)
    d["inlier_ratio"] = round(m.inlier_ratio, 4)
    d["ms"] = round(d["ms"], 1)
    return d

