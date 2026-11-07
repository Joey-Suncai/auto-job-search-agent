# sync_results.test_data(cx, runner) — when a submit is NOT written to the tracker (JSA-146)
- cx = the CX_DATA environment value (may be None or ""), runner = the real data/runner path.
- None or "" → False (normal run, the tracker row is written).
- A path that resolves to the same folder as `runner` → False: "~" is expanded, a trailing "/" is ignored, symlinks and
  ".." are resolved (compare real paths).
- Any other path (a temp folder, a test fixture folder, a sibling such as ".../data/runner_test") → True (test mode, no tracker row).
