#!/usr/bin/env python3
"""Train and calibrate the mini-PIGEON region head (TASKS.md T37, PLAN.md 4.2) -> Data/osv5m/head/.

A linear layer on the frozen PE-Core bank embeddings (tools/embed_bank.py), one class per
"<country>:<region>" of the OSV-5M `region` column: PT districts plus Madeira and the Azores, ES
autonomous communities, FR regions (pre-2016). Trained on the `train` partition only, with class
weights (n_c / mean n)^-CLASS_WEIGHT_POWER so that Madeira (the largest PT class) or Catalonia do not
dominate and the Azores or Alsace still count. Early-stopped on the class-weighted `val` loss, then
one temperature is fitted on `val` (grid search on unweighted NLL). The `test` partition is never read.

Saved to Data/osv5m/head/:
  head.npz          W (C x 1024), b, temperature, class names, embed_version
  classes.json      per class: name, country, region, n_train, lat/lon (the training image with the highest
                    mean non-urban theta to the region's images), extent_m (80th percentile distance)
  train_ids.txt.gz  the training image ids
  report.json       settings, timings, val top-1/top-4 (per image and macro), calibration, and the
                    Panoramax val panoramas (runtime views averaged; region = that of the nearest bank image)

Usage: .venv/bin/python tools/train_region_head.py [--epochs 60] [--lr 1e-3] [--wd 1e-4]
"""
import argparse
import gzip
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from panoloc import retrieval  # noqa: E402

CLASS_WEIGHT_POWER = 0.5
EXTENT_QUANTILE = 0.8
EARTH_R = 6_371_000.0


def haversine_matrix(a, b):
    """Distances in metres between rows of a (N x 2 lat/lon degrees) and b (M x 2)."""
    a, b = np.radians(a), np.radians(b)
    dlat = b[None, :, 0] - a[:, None, 0]
    dlon = b[None, :, 1] - a[:, None, 1]
    h = np.sin(dlat / 2) ** 2 + np.cos(a[:, None, 0]) * np.cos(b[None, :, 0]) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_R * np.arcsin(np.sqrt(np.clip(h, 0, 1)))


def class_point(coords, rng, n_cand=1500, n_ref=5000):
    """The training image with the highest mean non-urban theta to the class's images, and the extent."""
    cand = coords[rng.choice(len(coords), min(n_cand, len(coords)), replace=False)]
    ref = coords[rng.choice(len(coords), min(n_ref, len(coords)), replace=False)]
    theta = np.zeros(len(cand))
    for i in range(0, len(cand), 250):
        theta[i:i + 250] = (2 / (1 + haversine_matrix(cand[i:i + 250], ref) / 10_000)).mean(axis=1)
    best = cand[int(np.argmax(theta))]
    extent = float(np.quantile(haversine_matrix(best[None], coords)[0], EXTENT_QUANTILE))
    return best, max(extent, 1000.0), float(theta.max())


def topk_acc(probs, y, k):
    top = np.argsort(-probs, axis=1)[:, :k]
    return float(np.mean([yi in t for yi, t in zip(y, top)]))


def macro_acc(probs, y, n_classes, k=1):
    top = np.argsort(-probs, axis=1)[:, :k]
    hits = np.array([yi in t for yi, t in zip(y, top)])
    return float(np.mean([hits[y == c].mean() for c in range(n_classes) if (y == c).any()]))


def softmax(logits):
    z = logits - logits.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def nll(logits, y):
    return float(-np.log(softmax(logits)[np.arange(len(y)), y] + 1e-12).mean())


def ece(probs, y, bins=15):
    conf, pred = probs.max(axis=1), probs.argmax(axis=1)
    edges = np.linspace(0, 1, bins + 1)
    return float(sum(abs((pred[m] == y[m]).mean() - conf[m].mean()) * m.mean()
                     for lo, hi in zip(edges[:-1], edges[1:]) for m in [(conf > lo) & (conf <= hi)] if m.any()))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--wd", type=float, default=1e-4)
    ap.add_argument("--batch", type=int, default=1024)
    ap.add_argument("--patience", type=int, default=6)
    ap.add_argument("--out", type=Path, default=retrieval.HEAD_DIR)
    args = ap.parse_args(argv)
    torch.set_num_threads(4)
    torch.manual_seed(0)
    rng = np.random.default_rng(0)
    args.out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    tr_meta, tr_emb = retrieval.load_embeddings(partitions=("train",), dtype=np.float32)
    va_meta, va_emb = retrieval.load_embeddings(partitions=("val",), dtype=np.float32)
    names_tr = (tr_meta["country"] + ":" + tr_meta["region"]).to_numpy()
    names_va = (va_meta["country"] + ":" + va_meta["region"]).to_numpy()
    classes = sorted(set(names_tr))
    cidx = {c: i for i, c in enumerate(classes)}
    keep_va = np.isin(names_va, classes)
    y_tr = np.array([cidx[c] for c in names_tr])
    y_va = np.array([cidx[c] for c in names_va[keep_va]])
    va_emb = va_emb[keep_va]
    n_c = np.bincount(y_tr, minlength=len(classes))
    w_c = (n_c / n_c.mean()) ** -CLASS_WEIGHT_POWER
    w_c = w_c / (w_c * n_c).sum() * n_c.sum()
    print(f"{len(classes)} classes, {len(y_tr)} train, {len(y_va)} val ({time.time() - t0:.0f} s)", flush=True)

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    Xtr, Ytr = torch.from_numpy(tr_emb).to(dev), torch.from_numpy(y_tr).to(dev)
    Xva, Yva = torch.from_numpy(va_emb).to(dev), torch.from_numpy(y_va).to(dev)
    wt = torch.tensor(w_c, dtype=torch.float32, device=dev)
    head = torch.nn.Linear(retrieval.EMBED_DIM, len(classes)).to(dev)
    opt = torch.optim.AdamW(head.parameters(), lr=args.lr, weight_decay=args.wd)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, args.epochs)
    best, best_state, bad, history = float("inf"), None, 0, []
    for epoch in range(args.epochs):
        head.train()
        perm = torch.randperm(len(Xtr), device=dev)
        for i in range(0, len(perm), args.batch):
            j = perm[i:i + args.batch]
            # the scale lets a plain linear layer reach confident logits on unit-norm inputs
            loss = torch.nn.functional.cross_entropy(head(Xtr[j] * 30), Ytr[j], weight=wt)
            opt.zero_grad()
            loss.backward()
            opt.step()
        sched.step()
        head.eval()
        with torch.no_grad():
            vl = torch.nn.functional.cross_entropy(head(Xva * 30), Yva, weight=wt).item()
            acc = (head(Xva * 30).argmax(1) == Yva).float().mean().item()
        history.append({"epoch": epoch + 1, "val_weighted_ce": round(vl, 4), "val_top1": round(acc, 4)})
        print(f"epoch {epoch + 1}: val weighted CE {vl:.4f}, top-1 {acc:.4f}", flush=True)
        if vl < best - 1e-4:
            best, bad = vl, 0
            best_state = {k: v.detach().clone() for k, v in head.state_dict().items()}
        else:
            bad += 1
            if bad >= args.patience:
                break
    head.load_state_dict(best_state)
    W = (head.weight.detach().cpu().numpy() * 30).astype(np.float32)  # fold the input scale into W
    b = head.bias.detach().cpu().numpy().astype(np.float32)
    train_s = time.time() - t0

    logits_va = va_emb @ W.T + b
    temps = np.geomspace(0.2, 5, 241)
    temperature = float(temps[int(np.argmin([nll(logits_va / t, y_va) for t in temps]))])
    p_raw, p_cal = softmax(logits_va), softmax(logits_va / temperature)

    class_docs = []
    coords_tr = tr_meta[["lat", "lon"]].to_numpy()
    for i, name in enumerate(classes):
        pt, extent, th = class_point(coords_tr[y_tr == i], rng)
        country, region = name.split(":", 1)
        class_docs.append({"name": name, "country": country, "region": region, "n_train": int(n_c[i]),
                           "class_weight": round(float(w_c[i]), 4), "lat": round(float(pt[0]), 6),
                           "lon": round(float(pt[1]), 6), "extent_m": round(extent), "mean_theta_non_urban": round(th, 4)})

    np.savez(args.out / "head.npz", W=W, b=b, temperature=temperature, classes=np.array(classes),
             embed_version=retrieval.EMBED_VERSION)
    (args.out / "classes.json").write_text(json.dumps({"embed_version": retrieval.EMBED_VERSION, "classes": class_docs}, indent=1))
    with gzip.open(args.out / "train_ids.txt.gz", "wt") as f:
        f.write("\n".join(tr_meta["id"]) + "\n")

    report = {"embed_version": retrieval.EMBED_VERSION, "n_classes": len(classes), "n_train": len(y_tr),
              "n_val": len(y_va), "class_weight_power": CLASS_WEIGHT_POWER, "input_scale": 30,
              "lr": args.lr, "wd": args.wd, "batch": args.batch, "epochs_run": len(history),
              "best_val_weighted_ce": round(best, 4), "train_seconds": round(train_s, 1), "temperature": temperature,
              "val": {"top1": topk_acc(p_cal, y_va, 1), "top4": topk_acc(p_cal, y_va, 4),
                      "macro_top1": macro_acc(p_cal, y_va, len(classes)), "macro_top4": macro_acc(p_cal, y_va, len(classes), 4),
                      "nll_raw": nll(logits_va, y_va), "nll_calibrated": nll(logits_va / temperature, y_va),
                      "ece_raw": ece(p_raw, y_va), "ece_calibrated": ece(p_cal, y_va),
                      "per_class_top1": {c: round(float((p_cal[y_va == i].argmax(1) == i).mean()), 3)
                                         for i, c in enumerate(classes) if (y_va == i).any()}},
              "history": history}
    report["panoramax_val"] = panoramax_eval(retrieval.RegionHead(W, b, temperature, class_docs), classes)
    (args.out / "report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps({k: v for k, v in report.items() if k != "history"}, indent=1))


def panoramax_eval(head, classes):
    """Top-1/top-4 region accuracy on Panoramax val, views averaged; label = region of the nearest bank image."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from eval_knn import PMX_CACHE, panoramax_val
    df = panoramax_val()
    z = np.load(PMX_CACHE)
    if z["ids"].tolist() != df["id"].astype(str).tolist():
        return {"error": "panoramax cache does not match the val split"}
    meta = retrieval.read_partitions()
    meta = meta[meta["partition"].isin(["train", "val"])]
    bank_xy = meta[["lat", "lon"]].to_numpy()
    d = haversine_matrix(df[["lat", "lon"]].to_numpy(), bank_xy)
    nearest = d.argmin(axis=1)
    labels = (meta["country"].to_numpy()[nearest] + ":" + meta["region"].to_numpy()[nearest])
    out = {"label_source": "region of the nearest OSV-5M train/val image",
           "nearest_km_median": round(float(np.median(d.min(axis=1)) / 1000), 2)}
    for key in [k for k in z.files if k.startswith("emb_")]:
        views = z[key].astype(np.float32)
        hits1 = hits4 = 0
        per_country = {}
        for v, lab, c in zip(views, labels, df["country"]):
            ranked = [f"{country}:{region}" for region, country, _ in head.predict(v, top=4)]
            h1, h4 = ranked[0] == lab, lab in ranked
            hits1 += h1
            hits4 += h4
            pc = per_country.setdefault(c, [0, 0, 0])
            pc[0] += h1
            pc[1] += h4
            pc[2] += 1
        out[key.replace("emb_", "crop=").replace("4x3", "4:3")] = {
            "n": len(df), "top1": round(hits1 / len(df), 4), "top4": round(hits4 / len(df), 4),
            "by_country": {c: {"top1": round(a / n, 4), "top4": round(b / n, 4), "n": n} for c, (a, b, n) in per_country.items()}}
    return out


if __name__ == "__main__":
    main()
