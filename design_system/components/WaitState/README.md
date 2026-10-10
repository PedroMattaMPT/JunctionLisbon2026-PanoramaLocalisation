# WaitState

A real wait: names what is running, shows real elapsed time against the real deadline, and counts partial results. No spinner, no percentage.

- **Provide:** `what`, `who` (model), `elapsed`, `deadline` (seconds), optional `partial` ("4 of 11 checklist items answered so far"), `fallback`.
- Only for waits the backend reports; never invent progress.
