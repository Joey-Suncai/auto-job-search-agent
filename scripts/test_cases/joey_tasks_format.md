Return {"cases": [...]}. Each case is one of:
1. {"name": "...", "fn": "joey_tasks", "args": {"needs_user": [{"label": str}, ...] or null}, "expect": [str, ...], "spec_quote": "...", "ambiguous": false}
2. {"name": "...", "fn": "is_test_batch", "args": {"batch": {...}}, "expect": bool, "spec_quote": "...", "ambiguous": false}
3. {"name": "...", "fn": "joey_gate", "args": {"row": {...}, "needs_user": [{"label": str}, ...], "test": bool}, "expect": {row after}, "spec_quote": "...", "ambiguous": false}
Write 24 cases: joey_tasks 12 (Loom link, HireVue, "record a 60-second video", near misses: "videos" alone, Bloomberg,
"recorded transcript"? — decide by the rule, ratings, GPA, mixed list order), is_test_batch 5, joey_gate 7.
