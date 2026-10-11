#!/usr/bin/env python3
"""Embed every OSV-5M bank image with PE-Core (TASKS.md T21, T35; PLAN.md 4.1) -> Data/osv5m/emb/.

Every row of Data/osv5m/partitions.csv (tools/bank_partitions.py) is embedded, test and dropped
images included: test embeddings are needed for evaluation, and panoloc.retrieval.Bank keeps them
out of the gallery by partition. Rows are sorted by id and cut into fixed shards, so a rerun skips
every complete shard and resumes at the first missing one. Each shard is written to a temporary file
and renamed when complete.
  shard_NNNNN.npz   ids (str), emb (N x 1024 float16, L2-normalised), ok (bool: False = unreadable
                    image, embedding left at zero)
  manifest.json     model id, preprocessing, dtype, version string, shard size, row count, timings
The model and preprocessing come from panoloc.retrieval.PECore, the same code that embeds the
panorama views at run time. Verify with --verify: one embedding per partitions row, unique ids,
unit norms, no NaN.

Usage (from the repo root; HF_HUB_OFFLINE=1 is set by the script):
  .venv/bin/python tools/embed_bank.py --bench 512          # throughput only, writes nothing
  setsid nohup .venv/bin/python tools/embed_bank.py > Data/osv5m/emb/embed.log 2>&1 &
  .venv/bin/python tools/embed_bank.py --verify
Options: --batch 64 --workers 6 --shard-size 4096 --out Data/osv5m/emb
"""
import argparse
import datetime
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from panoloc.retrieval import EMB_DIR, EMBED_DIM, EMBED_VERSION, MODEL_ID, OSV_DIR, PARTITIONS_CSV, PREPROCESS  # noqa: E402


def rows():
    df = pd.read_csv(PARTITIONS_CSV, dtype={"id": str}, usecols=["id", "subdir"])
    return df.sort_values("id", kind="stable").reset_index(drop=True)


class Images:
    """torch Dataset over (id, subdir) rows -> (tensor, ok)."""

    def __init__(self, ids, subdirs, preprocess):
        self.ids, self.subdirs, self.preprocess = ids, subdirs, preprocess

    def __len__(self):
        return len(self.ids)

    def __getitem__(self, i):
        import torch
        from PIL import Image
        try:
            with Image.open(OSV_DIR / "images" / self.subdirs[i] / f"{self.ids[i]}.jpg") as im:
                return self.preprocess(im.convert("RGB")), True
        except Exception as e:  # a corrupt file must not stop the run; it is flagged in `ok`
            print(f"unreadable {self.subdirs[i]}/{self.ids[i]}: {e}", file=sys.stderr, flush=True)
            return torch.zeros(3, *PREPROCESS["resize"]), False


def loader(model, ids, subdirs, batch, workers):
    import torch
    ds = Images(list(ids), list(subdirs), model.preprocess)
    return torch.utils.data.DataLoader(ds, batch_size=batch, num_workers=workers, pin_memory=True,
                                       persistent_workers=False, prefetch_factor=4 if workers else None)


def embed_rows(model, ids, subdirs, batch, workers):
    embs, oks = [], []
    for x, ok in loader(model, ids, subdirs, batch, workers):
        embs.append(model.embed_tensor(x).numpy().astype(np.float16))
        oks.append(ok.numpy())
    return np.concatenate(embs), np.concatenate(oks)


def write_manifest(out, n_rows, shard_size, args, extra=None):
    import open_clip
    import torch
    doc = {"model_id": MODEL_ID, "tower": "vision only (open_clip model.visual)", "embed_dim": EMBED_DIM,
           "dtype_compute": "float16", "dtype_stored": "float16", "normalised": "L2, computed in float32 before storage",
           "preprocess": PREPROCESS, "version": EMBED_VERSION, "order": "partitions.csv rows sorted by id",
           "shard_size": shard_size, "n_rows": n_rows, "n_shards": -(-n_rows // shard_size),
           "partitions": str(PARTITIONS_CSV.relative_to(PARTITIONS_CSV.parents[2])),
           "torch": torch.__version__, "open_clip": open_clip.__version__,
           "batch": args.batch, "workers": args.workers,
           "written": datetime.datetime.now().isoformat(timespec="seconds"), **(extra or {})}
    (out / "manifest.json").write_text(json.dumps(doc, indent=2))


def verify(out):
    man = json.loads((out / "manifest.json").read_text())
    df = rows()
    ids, bad, n_nan, norms = [], 0, 0, []
    for k in range(man["n_shards"]):
        with np.load(out / f"shard_{k:05d}.npz") as z:
            e = z["emb"].astype(np.float32)
            ids.extend(z["ids"].tolist())
            bad += int((~z["ok"]).sum())
            n_nan += int(np.isnan(e).sum())
            norms.append(np.linalg.norm(e[z["ok"]], axis=1))
    norms = np.concatenate(norms)
    report = {"rows": len(df), "embeddings": len(ids), "unique_ids": len(set(ids)),
              "same_ids_as_partitions": ids == df["id"].tolist(), "unreadable": bad, "nan": n_nan,
              "norm_min": float(norms.min()), "norm_max": float(norms.max())}
    print(json.dumps(report, indent=2))
    ok = (report["same_ids_as_partitions"] and report["unique_ids"] == len(df) and n_nan == 0
          and abs(report["norm_min"] - 1) < 1e-2 and abs(report["norm_max"] - 1) < 1e-2)
    print("VERIFIED" if ok else "FAILED")
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=EMB_DIR)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--shard-size", type=int, default=4096)
    ap.add_argument("--bench", type=int, default=0, help="embed this many images, report img/s, write nothing")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.verify:
        sys.exit(0 if verify(args.out) else 1)

    from panoloc.retrieval import PECore
    df = rows()
    t0 = time.time()
    model = PECore()
    print(f"model loaded in {time.time() - t0:.1f} s on {model.device}", flush=True)

    if args.bench:
        import torch
        sub = df.sample(n=min(args.bench, len(df)), random_state=0)
        embed_rows(model, sub["id"][:args.batch], sub["subdir"][:args.batch], args.batch, 0)  # warm-up
        torch.cuda.synchronize()
        t = time.time()
        emb, ok = embed_rows(model, sub["id"], sub["subdir"], args.batch, args.workers)
        dt = time.time() - t
        rate = len(sub) / dt
        print(f"bench: {len(sub)} images in {dt:.1f} s = {rate:.1f} img/s; projected {len(df)} rows: "
              f"{len(df) / rate / 60:.1f} min; peak GPU {torch.cuda.max_memory_allocated() / 2**30:.2f} GiB")
        return

    n_shards = -(-len(df) // args.shard_size)
    write_manifest(args.out, len(df), args.shard_size, args, {"status": "running"})
    done = 0
    t_run = time.time()
    for k in range(n_shards):
        path = args.out / f"shard_{k:05d}.npz"
        part = df.iloc[k * args.shard_size:(k + 1) * args.shard_size]
        if path.exists():
            try:
                with np.load(path) as z:
                    if z["ids"].tolist() == part["id"].tolist():
                        continue
            except Exception:
                pass
            print(f"shard {k} does not match the rows: redoing it", flush=True)
        t = time.time()
        emb, ok = embed_rows(model, part["id"], part["subdir"], args.batch, args.workers)
        tmp = path.with_name(path.stem + ".tmp.npz")
        np.savez(tmp, ids=np.array(part["id"].tolist()), emb=emb, ok=ok)
        tmp.replace(path)
        done += len(part)
        rate = done / (time.time() - t_run)
        left = (len(df) - (k + 1) * args.shard_size) / rate if rate else 0
        print(f"shard {k + 1}/{n_shards}: {len(part)} in {time.time() - t:.0f} s, {rate:.1f} img/s, "
              f"~{max(left, 0) / 60:.0f} min left", flush=True)
    write_manifest(args.out, len(df), args.shard_size, args,
                   {"status": "complete", "seconds_this_run": round(time.time() - t_run, 1)})
    print("done", flush=True)
    verify(args.out)


if __name__ == "__main__":
    main()
