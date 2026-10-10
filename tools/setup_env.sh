#!/usr/bin/env bash
# Recreate the Python environment in .venv/ (gitignored) and download every model weight, so the pipeline runs offline.
# MODEL_DECISIONS.md has the model picks and pins. In this order:
#   1. a Python 3.12 venv with torch 2.11.0+cu128 / torchvision 0.26.0, the build verified on the RTX 5080 (sm_120)
#   2. every other package at the versions in requirements.lock.txt, installed under a torch constraint so nothing
#      can replace torch
#   3. Ultralytics and OpenVINO telemetry off; Ultralytics weights in ~/.cache/ultralytics/weights
#   4. weights, core first:
#        Ollama qwen3.5:9b; Hugging Face PE-Core-L14-336, CLIP ViT-L/14 (GeoCLIP), PLONK OSV-5M + YFCC, StreetCLIP
#        (PLONK OSV-5M's encoder); RapidOCR PP-OCRv6-medium + PP-OCRv5 Latin (ONNX, run with OpenVINO on the CPU);
#        torch.hub MegaLoc, ALIKED + LightGlue, DINOv2 ViT-L/14-reg (PLONK YFCC's encoder)
#      then optional: YOLOE-26-L + its MobileCLIP2 text encoder, SAM3-LiteText-S0, EoMT-L ADE20K (DINOv3 and DINOv2),
#      SigLIP 2 So400m/16-512
# Safe to re-run: installed packages and finished weights are skipped, but a weight file cut off mid-download starts
# again from zero. SKIP_WEIGHTS=1 installs packages only. On the venue Wi-Fi a single Hugging Face transfer fell
# below 1 MB/s on 2026-10-10 (about 25 GB of downloads in all): run this early, not right before a deadline.
# SAM3=1 also fetches the gated facebook/sam3, which needs approved access and `hf auth login` first.
# GeoCLIP's own heads and its 100k-point GPS gallery ship inside the geoclip wheel.
# Every cache is on disk (~/.cache/{uv,huggingface,torch,ultralytics}, Ollama's model dir): /tmp is a RAM tmpfs.
# Never install flash-attn, xformers, mmcv/mm*, detectron2, faiss-gpu, paddlepaddle-gpu, vllm, sglang, the official
# fasttext or gcld3: they break on sm_120 or NumPy 2. Never upgrade Ollama past 0.34.4 for the event.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/.venv"
PY="$VENV/bin/python"
LOCK="$ROOT/requirements.lock.txt"
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

retry() {  # retry <command...>: the venue Wi-Fi drops DNS and TLS now and then
  local n=0
  until "$@"; do
    n=$((n + 1)); [ "$n" -ge 6 ] && return 1
    echo "retry $n in $((n * 15)) s: $*" >&2; sleep $((n * 15))
  done
}

echo "### $(date -Is) python env"
[ -x "$PY" ] || uv venv --python 3.12 "$VENV"
retry uv pip install --python "$PY" --index-url https://download.pytorch.org/whl/cu128 torch==2.11.0 torchvision==0.26.0
printf 'torch==2.11.0\ntorchvision==0.26.0\n' > "$TMP/torch.txt"
if [ -f "$LOCK" ]; then
  grep -vE '^(torch|torchvision)==' "$LOCK" > "$TMP/req.txt"
else  # no lock: the top-level picks
  cat > "$TMP/req.txt" <<'EOF'
transformers==5.19.0
open_clip_torch==3.3.0
geoclip==1.2.3
diff-plonk==0.4
rapidocr==3.10.0
openvino==2026.4.1
ultralytics==8.4.175
clip @ git+https://github.com/ultralytics/CLIP.git
lightglue @ git+https://github.com/cvg/LightGlue
heliport==1.0.1
py3langid==0.4.0
pycld2==0.42
faiss-cpu==1.15.1
py360convert==1.0.4
pvlib==0.16.1
huggingface_hub==1.33.0
osmium==4.3.1
shapely==2.2.0
pyproj==3.8.0
pyogrio==0.13.0
geopandas==1.2.0
rasterio==1.5.2
EOF
fi
retry uv pip install --python "$PY" -c "$TMP/torch.txt" -r "$TMP/req.txt"
"$PY" -c 'import torch; assert torch.__version__ == "2.11.0+cu128", torch.__version__; print("torch", torch.__version__, "cuda ok:", torch.cuda.is_available())'

echo "### $(date -Is) telemetry off, ultralytics weights dir"
mkdir -p "$HOME/.cache/ultralytics/weights"
"$VENV/bin/yolo" settings sync=False weights_dir="$HOME/.cache/ultralytics/weights" > /dev/null
"$VENV/bin/opt_in_out" --opt_out > /dev/null  # OpenVINO counts a missing consent file as consent

[ "${SKIP_WEIGHTS:-0}" = 1 ] && { echo "### $(date -Is) done (SKIP_WEIGHTS=1)"; exit 0; }

echo "### $(date -Is) ollama qwen3.5:9b"
ollama --version
ollama list | grep -q '^qwen3\.5:9b ' || retry ollama pull qwen3.5:9b

echo "### $(date -Is) hugging face weights"
"$PY" -I - <<'EOF'
import os, time
from huggingface_hub import snapshot_download
W = ["*.json", "*.txt", "*.model"]  # configs and tokenizers; the weight patterns skip duplicate .bin/TF/Flax copies
JOBS = [
    ("timm/PE-Core-L-14-336", W + ["open_clip_model.safetensors"]),
    ("openai/clip-vit-large-patch14", W + ["model.safetensors"]),  # GeoCLIP backbone
    ("nicolas-dufour/PLONK_OSV_5M", None),
    ("nicolas-dufour/PLONK_YFCC", None),
    ("geolocal/StreetCLIP", None),  # PLONK OSV-5M's image encoder; only ships pytorch_model.bin
    ("tue-mps/eomt-dinov3-ade-semantic-large-512", None),
    ("tue-mps/ade20k_semantic_eomt_large_512", W + ["model.safetensors"]),
    ("vil-uob/sam3-litetext-s0", None),
    ("google/siglip2-so400m-patch16-512", None),
]
if os.environ.get("SAM3") == "1":
    JOBS.append(("facebook/sam3", W + ["model.safetensors"]))
failed = []
for repo, pats in JOBS:
    for attempt in range(6):
        try:
            print("ok", repo, snapshot_download(repo, allow_patterns=pats), flush=True); break
        except Exception as e:
            print(f"retry {repo}: {type(e).__name__}: {str(e)[:200]}", flush=True); time.sleep(15 * (attempt + 1))
    else:
        failed.append(repo)
if failed:
    raise SystemExit(f"failed: {failed}")
EOF

echo "### $(date -Is) rapidocr models (into .venv/.../rapidocr/models)"
"$PY" -I - <<'EOF'
from rapidocr import RapidOCR
from rapidocr.utils.typings import EngineType, LangDet, LangRec, ModelType, OCRVersion
OV = EngineType.OPENVINO
for v, mt, det_lang, rec_lang in ((OCRVersion.PPOCRV6, ModelType.MEDIUM, "pt", "pt"),                  # PP-OCRv6-medium, multilingual
                                  (OCRVersion.PPOCRV5, ModelType.MOBILE, LangDet.MULTI, LangRec.LATIN)):  # fallback: PP-OCRv5 Latin
    RapidOCR(params={"Det.engine_type": OV, "Det.ocr_version": v, "Det.model_type": mt, "Det.lang_type": det_lang,
                     "Rec.engine_type": OV, "Rec.ocr_version": v, "Rec.model_type": mt, "Rec.lang_type": rec_lang,
                     "Cls.engine_type": OV, "Global.log_level": "warning"})
print("ok rapidocr")
EOF

echo "### $(date -Is) torch.hub and github weights"
CUDA_VISIBLE_DEVICES="" "$PY" -I - <<'EOF'
import os, time, torch
def megaloc(): torch.hub.load("gmberton/MegaLoc", "get_trained_model", trust_repo=True)
def dinov2_reg(): torch.hub.load("facebookresearch/dinov2", "dinov2_vitl14_reg", trust_repo=True)  # PLONK YFCC encoder
def lightglue():
    from lightglue import ALIKED, LightGlue
    ALIKED(max_num_keypoints=1024); LightGlue(features="aliked")
def yoloe():  # set_classes() loads mobileclip2_b.ts; both resolve from the weights_dir setting at run time
    from ultralytics.utils import SETTINGS
    from ultralytics.utils.downloads import attempt_download_asset
    os.chdir(SETTINGS["weights_dir"])
    for f in ("yoloe-26l-seg.pt", "mobileclip2_b.ts"):
        assert os.path.getsize(attempt_download_asset(f)) > 1e6, f
failed = []
for name, fn in (("megaloc", megaloc), ("lightglue", lightglue), ("dinov2_vitl14_reg", dinov2_reg), ("yoloe", yoloe)):
    for attempt in range(6):
        try:
            fn(); print("ok", name, flush=True); break
        except Exception as e:
            print(f"retry {name}: {type(e).__name__}: {str(e)[:200]}", flush=True); time.sleep(15 * (attempt + 1))
    else:
        failed.append(name)
if failed:
    raise SystemExit(f"failed: {failed}")
EOF

echo "### $(date -Is) done"
