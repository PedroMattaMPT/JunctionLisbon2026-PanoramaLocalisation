# StreetCLIP baseline

A separate, zero-shot fallback: [StreetCLIP](https://huggingface.co/geolocal/StreetCLIP) scores 8 horizontal views of a panorama against "A Street View photo close to {place}, {region}, {country}" prompts over a GeoNames gazetteer of Portugal, Spain and France, hierarchically (country, then region, then place), and returns the top places' coordinates. It isn't part of the main pipeline in `panoloc/`. The method and options are in the docstring of `geolocate.py`.

```bash
.venv/bin/python streetclip/geolocate.py "Data/Panorama Warm-Up" -o streetclip/results/streetclip_predictions.json
```

The first run downloads the GeoNames files and caches the prompt embeddings in `cache/streetclip/` (gitignored).

| Results | Panoramas |
|---|---|
| `results/streetclip_predictions.json` | the first warm-up set, `Data/Panorama Warm-Up/` |
| `results/streetclip_predictions_hard.json` | the second warm-up set, recorded as `Data/Panorama Hard/` (kept out of git; `Data/Panorama Warm-Up2/` locally) |
