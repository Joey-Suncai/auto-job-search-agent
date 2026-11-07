# SuccessFactors runner helpers

## parse_job(url) -> {"host", "id"} | null
"https://<host>/[<one path segment>/]job/<slug>/<7 or more digits>[/][?…|#…]" → {"host": host in lower case, "id": digits}.
Examples: careers.hfsinclair.com/job/Dallas-IT-Data-Analytics-Intern-TX-75219/1430072400/ ; jobs.grainger.com/ImperialSupplies/job/GREEN-BAY-X/1234567/ .
Anything else (fewer than 7 digits, no /job/, two extra path segments before job, not http) → null.

## clean_label(text) -> str
Collapse whitespace, drop a leading "*" (and spaces after it), a trailing "*" (an employer "Address Line1*", 2026-11-04) and a trailing ":" (and spaces before it), trim.

## attached_name(page_text, index) -> str
index 0 = resume, 1 = cover letter. In the page text (whitespace collapsed), "Resume Download document <name>" (index 0)
or "Cover letter Download document <name>" (index 1), where <name> is a run of non-space characters ending in .pdf, .doc,
.docx, .txt or .rtf (case-insensitive) → <name>. Nothing attached / other index → "".

## other_text(label) -> bool  (an "Other" follow-up box)
True when the label starts with "If Other" or "If Other Source" and within 40 characters says specify / explain / list /
enter; or starts with "Other" and within 30 characters says "free text" / "specify" / "please"; or starts with
"Please specify". Case-insensitive. False otherwise ("If Employee Referral, list employee's name here", "Other Name(s) known by").
