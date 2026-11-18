Write a JSON list of cases. Each case is one of three kinds:
{"name": str, "fn": "gh_verdict", "statuses": [int,...], "expect": "open"|"closed"|"unknown"}
{"name": str, "fn": "board_verdict", "platform": "lever"|"ashby", "status": int, "body": str (the raw response text), "job_id": str, "expect": "open"|"closed"|"unknown"}
{"name": str, "fn": "mark_closed_row", "row": {"id":..., "elig":..., "tier":..., "tier_orig":... (optional)}, "why": str, "source": str, "today": "YYYY-MM-DD",
 "expect": {"changed": bool, "elig": str, "tier": str, "elig_closed": {"at":..,"why":..,"source":..} or null (when unchanged), "tier_orig": str or null}}
Always include "spec_quote".
