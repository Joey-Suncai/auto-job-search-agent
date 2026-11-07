A JSON array of 30 cases, each one of:
{"name", "fn": "company_link", "args": {"href": str}, "expect": str}
{"name", "fn": "resolve", "args": {"info": {...}}, "expect": {"li_apply": str, "apply_url": str, "ats_url": str}}
{"name", "fn": "apply_row", "args": {"row": {...}, "res": {"li_apply", "reason", "apply_url", "ats_url"}, "li_url": str, "today": "2026-11-05"}, "expect": {<the whole row after the call>}}
{"name", "fn": "targets", "args": {"rows": [...], "wellfound_pages": [...], "redo": bool}, "expect": [[id, job id], …]}
About 8 company_link, 10 resolve (closed, easy by text, easy by aria only, external Workday posting, external Workday
home page, Greenhouse gh_jid, a company careers site, hidden control before visible, applied, no controls), 6 apply_row,
6 targets (ordering, Wellfound pages, skips, redo). Row ids look like "J00123". Use real-looking URLs.
