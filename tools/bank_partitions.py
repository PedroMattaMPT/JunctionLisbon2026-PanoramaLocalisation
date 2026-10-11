#!/usr/bin/env python3
"""Declare the OSV-5M bank partitions (TASKS.md T34, PLAN.md 4.1-4.2) -> Data/osv5m/partitions.csv.

One row per downloaded image: id, country, region, lat, lon, partition, group, subdir.
  partition  test     the official OSV-5M test split (5,206): the final external test. Never in the
                      retrieval gallery, never in training or calibration (PLAN.md 4.6).
             train    reference gallery and mini-PIGEON training
             val      about 10% of the training groups, per region: kNN and head early stopping,
                      temperature calibration, aggregation choices. Also in the default gallery.
             dropped  Ceuta and Melilla (Spain, in Africa: outside the challenge region)
  group      PT: "seq:<sequence id>". ES/FR have no sequence column, so "blk:<row>:<col>", a ~10 km
             block: row = floor(lat_km / 10), col = floor(lon_km / 10) with lon_km measured at the
             centre latitude of its row. A border block can hold both ES and FR images.
  subdir     the image folder under Data/osv5m/images/ (test, train_PT, train_ESFR)

Validation groups are drawn per region (the majority region of a group's images), in a seeded random
order, until they hold at least VAL_FRACTION of that region's images. So every class, the islands
included, has validation images, and adjacent frames of one sequence never straddle train and val.
Neighbouring sequences on the same road can still fall on both sides: that mirrors a real bank,
which can cover the road a query was taken on, but not with the query's own capture.

Inputs: Data/osv5m/lists/osv5m_{train,test}_{PT,ES_FR}.csv.gz (metadata) and ids_*.txt (the ids
actually fetched). Every id must have an image file; missing files are reported and fail the run.

Usage: .venv/bin/python tools/bank_partitions.py [--val-fraction 0.1] [--seed 0] [--block-km 10]
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OSV = ROOT / "Data" / "osv5m"
OUT = OSV / "partitions.csv"
VAL_FRACTION = 0.10
BLOCK_KM = 10.0
KM_PER_DEG = 111.32
DROP_REGIONS = {"Ceuta", "Melilla"}
COLUMNS = ["id", "country", "region", "lat", "lon", "partition", "group", "subdir"]


def block_key(lat, lon, block_km=BLOCK_KM):
    """The ~block_km spatial block of a point, as "blk:<row>:<col>"."""
    row = math.floor(lat * KM_PER_DEG / block_km)
    centre_lat = (row + 0.5) * block_km / KM_PER_DEG
    col = math.floor(lon * KM_PER_DEG * math.cos(math.radians(centre_lat)) / block_km)
    return f"blk:{row}:{col}"


def assign_val(groups, regions, fraction=VAL_FRACTION, seed=0):
    """Pick validation groups per region until each region has >= fraction of its images in val.

    groups, regions: one entry per image. Returns the set of validation group keys.
    """
    df = pd.DataFrame({"group": groups, "region": regions})
    sizes = df.groupby("group").size()
    major = df.groupby("group")["region"].agg(lambda s: s.value_counts().index[0])
    rng = np.random.default_rng(seed)
    val = set()
    for region in sorted(major.unique()):
        keys = sorted(major.index[major == region])
        target = fraction * sizes[keys].sum()
        taken = 0
        for i in rng.permutation(len(keys)):
            if taken >= target:
                break
            val.add(keys[i])
            taken += sizes[keys[i]]
    return val


def load(lists=OSV / "lists"):
    """Metadata of every fetched image, with country, region, lat, lon, sequence (PT only) and subdir."""
    pt_cols = {"latitude": "lat", "longitude": "lon"}
    ids_esfr = set((lists / "ids_train_ESFR_sample.txt").read_text().split())
    frames = []
    for name, subdir, keep in [("osv5m_train_PT", "train_PT", None), ("osv5m_train_ES_FR", "train_ESFR", ids_esfr),
                               ("osv5m_test_PT", "test", None), ("osv5m_test_ES_FR", "test", None)]:
        df = pd.read_csv(lists / f"{name}.csv.gz", dtype={"id": str, "sequence": str}).rename(columns=pt_cols)
        if keep is not None:
            df = df[df["id"].isin(keep)]
        if "sequence" not in df:
            df["sequence"] = None
        df["subdir"] = subdir
        df["source"] = "test" if subdir == "test" else "train"
        frames.append(df[["id", "country", "region", "lat", "lon", "sequence", "subdir", "source"]])
    return pd.concat(frames, ignore_index=True)


def build(meta, val_fraction=VAL_FRACTION, seed=0, block_km=BLOCK_KM):
    """Partition and group the metadata rows (see the module docstring)."""
    meta = meta.copy()
    meta["region"] = meta["region"].fillna("").astype(str)
    has_seq = meta["sequence"].notna() & (meta["sequence"].astype(str) != "")
    meta["group"] = [f"seq:{s}" if ok else block_key(la, lo, block_km)
                     for s, ok, la, lo in zip(meta["sequence"], has_seq, meta["lat"], meta["lon"])]
    meta["partition"] = np.where(meta["source"] == "test", "test", "train")
    meta.loc[meta["region"].isin(DROP_REGIONS), "partition"] = "dropped"
    pool = meta["partition"] == "train"
    val = assign_val(meta.loc[pool, "group"].tolist(), meta.loc[pool, "region"].tolist(), val_fraction, seed)
    meta.loc[pool & meta["group"].isin(val), "partition"] = "val"
    return meta[COLUMNS]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--val-fraction", type=float, default=VAL_FRACTION)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--block-km", type=float, default=BLOCK_KM)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    meta = load()
    if not meta["id"].is_unique:
        sys.exit(f"duplicate ids in the metadata: {meta['id'][meta['id'].duplicated()].tolist()[:5]}")
    missing = [i for i, d in zip(meta["id"], meta["subdir"]) if not (OSV / "images" / d / f"{i}.jpg").is_file()]
    if missing:
        sys.exit(f"{len(missing)} metadata rows have no image, e.g. {missing[:5]}")
    parts = build(meta, args.val_fraction, args.seed, args.block_km)
    tmp = args.out.with_suffix(".csv.tmp")
    parts.to_csv(tmp, index=False)
    tmp.replace(args.out)

    print(f"wrote {args.out} ({len(parts)} rows)")
    print(parts.groupby(["country", "partition"]).size().unstack(fill_value=0).to_string())
    pool = parts[parts["partition"].isin(["train", "val"])]
    print("\ngroups in train/val:", pool.groupby("partition")["group"].nunique().to_dict())
    print("\nper region (train / val / test):")
    print(parts[parts["partition"] != "dropped"].groupby(["country", "region", "partition"]).size()
          .unstack(fill_value=0).to_string())
    print("\ndropped:", parts.loc[parts["partition"] == "dropped", "region"].value_counts().to_dict())


if __name__ == "__main__":
    main()
