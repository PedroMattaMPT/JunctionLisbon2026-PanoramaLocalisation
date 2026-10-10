# PanoramaStrip

The flat equirectangular panorama with overlay layers and the bearing ruler — the hero of the console.

- **Provide:** `c` (case: `scene` image, `detections`, `texts`, `sun`, `water`, `yawToBearing`, `yawToBearingErr`, `file`, `size`), `width`, `layers` {`sectors`, `mask`, `boxes`, `text`, `seg`, `sun`, `water`, `skyline`}, `selected`, `ruler` (`yaw` | `bearing` | false), `fov` (360 viewer window), `labelMode` (`all` | `selected` | `text`), `crop` (pitch range).
- Boxes are model observations (corner brackets); text boxes show the reading in mono; rejected boxes are dashed, struck and ghosted. Every stroke has a dark halo.
- In the app the image is the 6080×3040 JPG; the preview draws a procedural stand-in.
