Return {"cases": [...]}; each case:
{"name": "<unique>",
 "queue": ["- [ ] 2026-11-01T10:00:00 **2026-11-01_Acme_Data_Intern** — Workday needs answers: … — https://x", ...],
 "human_checks": [{"at": "...", "folder": "...", "state": "open"|"resolved", "checks": [{"question": "..."}]}],
 "apply_requests": [{"at": "...", "id": "J00001", "status": "queued"|"applying"|"needs-you"|"submitted"|"cancelled", "note": "..."}],
 "submitted": ["<folder>"], "tracker": {"<job id>": "<status>"}, "jobs": {"<job id>": "<eligibility>"}, "job_of": {"<folder>": "<job id>"},
 "expect": [{"folder": "<folder or job id>", "n": <int>, "kind": "<problem type>"}],   // the listed rows IN ORDER; [] = nothing listed
 "spec_quote": "...", "ambiguous": false}
Folder names look like 2026-11-01_Company_Role. Write ~20 cases.
