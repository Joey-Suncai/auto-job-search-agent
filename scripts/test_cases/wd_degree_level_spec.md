# Workday Degree dropdown: level-style options and multi-level options — spec (JSA-327, 2026-11-17)

Joey's education entries: UIUC is a bachelor's (B.A. Economics), UChicago a master's (M.S.). A Workday "Degree" dropdown lists
either named degrees ("Bachelor of Arts", "B.A.") or level-style labels. Real level-style lists seen:
Micron: "Master's Level Degree", "Bachelor's Level Degree"; Entrust: "4-year Degree (Bachelor's)",
"Post-Graduate Degree (Master's, PhD, JD, etc.)"; a Workday employer: "Undergraduate Degree", "Post Graduate Degree".

## bachelor_options(opts) -> list of options, best first (the first one is chosen)
- An option whose words are "bachelor" (also "bachelors", "bachelor's") plus only level filler words — level, degree, year, 4, four,
  undergraduate, a — is a plain bachelor's option ("Bachelor's Level Degree", "4-year Degree (Bachelor's)", "Bachelors Degree", "4 Year Bachelor's Degree"). It qualifies, ranked like a plain "Bachelor's".
- A named degree "Bachelor of Arts" / "B.A." ranks before a plain or level-style bachelor's option.
- "Bachelor of Science" / "B.S." alone is never his (not an arts degree) and is not returned, nor are specialty bachelor's
  (fine arts, music, nursing, engineering, BBA, business administration, technology, education, architecture, social work, applied science …).
- An option combining several degrees with "or" that names Arts qualifies after the plain ones; without Arts it does not.
- Options with no bachelor word ("Master's Level Degree", "Associate Degree", "Undergraduate Degree") are not returned by this function.
- Empty list → [].

## level_of(value) -> "phd" | "master" | "bachelor" | "other" | None  (block check: which level an option text means)
- "Undergraduate ..." → bachelor (checked before master, because "Undergraduate Degree" contains "graduate degree").
- A text naming master / post-graduate / graduate degree / M.S. / M.A. / MBA → master, even when the same text also lists PhD, JD or doctorate
  as examples ("Post-Graduate Degree (Master's, PhD, JD, etc.)" → master).
- Otherwise a text naming PhD / doctor / doctorate → phd.
- bachelor / B.A. / B.S. / baccalaureate (and "4-year Degree (Bachelor's)", "Bachelor's Level Degree") → bachelor.
- associate / high school / secondary / diploma / GED → other. Anything else → None.
