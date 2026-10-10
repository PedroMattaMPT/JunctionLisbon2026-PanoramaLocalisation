# MatchView

Exact spot: the query view and a geotagged reference photo side by side, keypoint matches drawn between them, inliers counted.

- **Provide:** `c` (case with `spot.refs`), optional `refIdx`, `width`, `height`, `lines` (sample size), `showRejected`.
- Accepted matches in `support`, rejected in dashed `contra`. A good match is not a 10 m camera fix: pair it with the remaining offset.
