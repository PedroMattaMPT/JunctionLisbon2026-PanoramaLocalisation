# Button

The one button: primary at most once per view, and any action that costs points shows its cost tag on the button itself.

- **Provide:** `children` (a verb: "Submit answer", "Send cue"), optional `icon`, `cost` (multiplier, e.g. 0.95), `shortcut`, `busy` (the real thing being waited for, with elapsed time), `disabled`.
- **Variants:** `primary` (ink fill; Submit, Start the run), `secondary` (outline; default), `quiet` (no edge; export, copy), `skip` (dashed, "free" tag, S key — only for Skip).
- **Do:** name the action the same way through the flow (Submit → "Submitted"). Put `cost` on every costing action.
- **Don't:** style Skip like "No" or "None of these"; use a spinner for `busy`; use more than one primary in a view.
