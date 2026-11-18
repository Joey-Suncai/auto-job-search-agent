A JSON object per case:
{"name": "short unique name", "kind": "stale",
 "input": {"last": {"read_at": "2026-11-06", "status": "ok",
                    "questions": [{"label": "School", "n_options": 60}],
                    "fields": 39},
           "today": "2026-11-10", "recheck_days": 5, "only_new": false},
 "expect": {"read": true, "cut": true},
 "spec_quote": "..."}
- In `last`, write an item's dropdown as "n_options": N (the harness builds a list of N options); an item without
  n_options has no options. Any of fields / questions / needs may be omitted, a number, or a list.
  "last" may be null. A list item may be a plain string.
- expect.read = due(); expect.cut = cut_options(last) (false when last is null).
