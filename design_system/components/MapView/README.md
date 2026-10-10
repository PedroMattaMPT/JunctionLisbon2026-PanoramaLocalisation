# MapView

The map (MapLibre in the app, bundled outlines when offline) with every data layer in a fixed order: base < heat < zones < points < rings < pins < final mark < labels.

- **Provide:** `view` {`lat`, `lng`, `span` (degrees of longitude across)}, `width`, `height`, and any of `heat` (blobs), `samples`, `refs`, `candidates`, `selected`, `rings` (`r` in metres or null), `zones` (`key`, `region` | `poly` | `rest`, `point`, `label`, `chosen`, `dim`), `cone`, `final`, `area`, `inset`, `offline`, `dimOthers`, `hoverRef`, `legend`, `scale`, `labels`.
- Zones never overlap and cover the scope; each shows a lettered key at a representative point that is not a camera position.
- Offline: "Tiles offline · bundled outlines of PT, ES, FR with district borders" — drawn on purpose, not as an error.
