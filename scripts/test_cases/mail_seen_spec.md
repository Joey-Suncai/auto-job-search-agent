# Application-status checks read each message once (JSA-140)

The e-mail and text checks now run every 30 minutes in the day. Each run fetches the last 2 days of messages; a record
of handled message ids (`seen`, a dict id → {"on": "YYYY-MM-DD", "kind": "done" | "unmatched", "apps": int}) makes sure
each message is handled once.

## run_new(items, apply, seen, notes, n_apps, reread=False, today)
- `items`: messages, each a dict with an "id". `apply(item)` handles one message and returns a result dict, or None
  (nothing to record in the tracker). A result with `"unmatched": true` is a job message that matched no application.
- `notes` is a dict; `apply` may append a line to `notes["fallback"]` (a list, created when missing) when the Claude
  read of that message failed.
- `n_apps`: number of application rows in the tracker now.
- An item is **skipped** (apply not called) when its id is in `seen` — except when that entry's kind is "unmatched"
  and n_apps is greater than the entry's "apps" (the tracker gained rows, so it may match now), or when `reread` is true.
- For every item that is handled (apply called): if apply added no new line to `notes["fallback"]`, `seen[id]` is set
  to {"on": today (ISO date), "apps": n_apps, "kind": "unmatched" if the result is a dict with unmatched true, else "done"}
  (a None result is "done"). If apply did add a fallback line, `seen` is not changed for that id (tried again next run).
- Returns (results, push, handled):
  - results: the non-None results, in item order;
  - push: the unmatched results that should be pushed to Joey — every unmatched result except one whose id was
    already recorded in `seen` as "unmatched" before this run (never pushed twice);
  - handled: number of items apply was called on.

## save_seen(path, seen, today) → kept
- Keeps only entries whose "on" is on or after today − 7 days (string compare of ISO dates); an entry without "on" is
  dropped. Writes the kept dict as JSON to `path` (creating the folder), and returns it.

## load_seen(path)
- Returns the JSON dict in `path`; a missing file or invalid JSON → {} (no error).
