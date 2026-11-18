# The Leadership section follows the fact's on_resume flag (JSA-255)

`lead_on_resume(entries, lead_org)`: `entries` = the `entries` list of the user's facts file (each a dict with `id`, `kind`,
`org`, optional `on_resume`); `lead_org` = the organisation named in the resume content's LEAD block (the Leadership section).
Returns False when a fact entry whose `org` equals `lead_org` (case-insensitive, whitespace collapsed) has `on_resume`
explicitly false — the user took that activity off every resume; the Leadership section is then left out of every resume.
Returns True otherwise: `on_resume` true, missing, or any value other than the boolean false; no entry with that org;
an empty or missing `lead_org` (then there is no section to decide); `entries` empty / None. When several entries share the
org, False if ANY of them is explicitly false. Entries of other orgs never matter. Only the boolean False counts: the
string "false", 0 and null do not.
