# SmartRecruiters runner helpers

## parse_posting(url) -> {"company", "id"} | {"company", "uuid"} | null
- `https://jobs.smartrecruiters.com/<Company>/<digits>` optionally followed by `-<slug>`, `/`, `?…` or `#…` (digits: 6 or
  more) → {"company": <Company>, "id": <digits>}. Also host `careers.smartrecruiters.com`. http or https.
- `https://jobs.smartrecruiters.com/oneclick-ui/company/<Company>/publication/<uuid>` (uuid = 36 chars, hex and dashes,
  any case; anything may follow) → {"company": <Company>, "uuid": <uuid in lower case>}.
- Anything else (other hosts, fewer than 6 digits, missing parts, "oneclick-ui" used as the company with digits) → null.

## clean_label(text) -> str
Collapse whitespace; drop a leading "*" (required star) and the space after it; drop a trailing character counter of the
form "<n> / <m>" (spaces optional); remove "(definitions)" / "(definition)" anywhere; trim.

## plan_questions(raw) -> list
raw = list of {idx, type, label, text, id, tag, required, radios, boxes}. Output one item per question, in order:
{key, label, type, required, options, tag}. Items with type "info", "files" or "file" are dropped. type mapping:
radio→radio, select→select, multiselect→select, text→text, number→text, date→text, textarea→textarea, checkbox→checkbox,
anything else→text. key = id, or "q<idx>" when id is empty. options = radios if non-empty, else boxes, else [].
label = clean_label(label, or text when label is empty), then if it ends with " <option>" for an option, that option text
is removed from the end (each option in order). required = bool(required).

## IF_OTHER (regex, case-insensitive) — matches labels that start with "If you selected Other", "If you chose Other",
"If you picked Other", "If you answered Other", "If other", "If you selected \"Other\"". Must not match labels that merely
contain "other" later ("Do you have other names?", "If hired, will you…").
