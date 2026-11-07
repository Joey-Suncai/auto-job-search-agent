A JSON array of 30 cases, each one of:
{"name", "fn": "skip_names", "args": {"text": str}, "expect": [str]}
{"name", "fn": "can_queue", "args": {"job": {...}, "applied_ids": [str], "skip": [str], "runner": {...}}, "expect": true|false}
{"name", "fn": "apply_mode", "args": {"job": {...}, "runner": {...}}, "expect": "runner"|"verify-first"|"by-hand"}
{"name", "fn": "set_fields", "args": {"job": {...}, "status": str, "now": str, "note": str, "by": str}, "expect": {<row>} or "error"}
{"name", "fn": "queued", "args": {"rows": [...]}, "expect": [[at, id, company, title], …]}
{"name", "fn": "validate", "args": {"method": str, "path": str, "headers": {...}, "body": str}, "expect": <status code int>}
About 3 skip_names, 9 can_queue (each check failing once, 待核实 ok, runner none ok, tiktok refused, cancelled ok), 6 apply_mode, 4
set_fields (note removed, by kept, bad status), 2 queued, 6 validate.
