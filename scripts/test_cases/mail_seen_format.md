Return {"cases": [...]}. Each case is one of:

1. {"name": "...", "fn": "run_new",
    "args": {"items": [{"id": str}, ...],
             "results": {id: result-or-null},      // what apply returns for each id; result = {"type": str} or {"unmatched": true}
             "fallback_ids": [id, ...],            // apply appends a notes["fallback"] line for these ids
             "seen": {id: {"on": str, "kind": "done"|"unmatched", "apps": int}},
             "n_apps": int, "reread": bool, "today": "YYYY-MM-DD"},
    "expect": {"results": [result, ...], "push": [result, ...], "handled": int,
               "called": [id, ...],                // ids apply was called on, in order
               "seen_after": {id: {...}}},
    "spec_quote": "...", "ambiguous": false}

2. {"name": "...", "fn": "save_seen", "args": {"seen": {...}, "today": "YYYY-MM-DD"}, "expect": {kept dict},
    "spec_quote": "...", "ambiguous": false}

3. {"name": "...", "fn": "load_seen", "args": {"file": str or null}, "expect": {...}, ...}   // file = raw file text, null = no file

Write 24 cases: run_new 17 (new item done / unmatched / None, seen done skipped, seen unmatched with same / more / fewer
apps, reread, fallback not recorded and retried, unmatched retried and still unmatched → not pushed, retried and now
matched, mixed order, empty items, duplicate ids in one run), save_seen 5 (boundary exactly 7 days, 8 days, missing on),
load_seen 2.
