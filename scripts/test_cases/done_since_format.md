A JSON array of 22 cases: {"name": str, "fn": "entries"|"since"|"new_since", "rows": [row dicts with job_id / company / title at the ROW level and action_done entries holding only on / action], "day": "YYYY-MM-DD" (since only), "before": [[on, job_id, company, title, action], ...] (new_since only), "expect": [[on, job_id, company, title, action], ...]}
About 9 entries, 6 since, 7 new_since. Cover: missing / null / empty lists, non-object entries, missing on, missing
company / title, sort ties, two entries in one row, boundary dates, duplicates, undo (entry gone), nothing new.
