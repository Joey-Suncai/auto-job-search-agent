# check_bullets.check_master — outcome-first rule (JSA-250, Joey 2026-11-09)

check_master(m) takes {"entries": [{"name": str, "bullets": [{"text": str}, ...]}]} and returns problem lines.
New rule "outcome_first": for each entry with 2 or more bullets, if the FIRST bullet's text contains no digit (0-9) and
at least one LATER bullet of that entry contains a digit, report one problem for that entry. Number words ("five",
"zero") are not digits. An entry with 0 or 1 bullet is never reported. An entry where no bullet has a digit is not
reported. An entry whose first bullet has a digit is not reported, whatever the later bullets hold. Each entry is judged
on its own bullets only.

The other page rules also apply to the same page (they report their own kinds):
- every bullet: the first word must be an action verb (a bullet opening with a context phrase — 2-16 words before the
  first comma/colon, first word to/when/with/after/because/as/for/... — is an "opener" problem) (past tense "-ed" or a known verb like
  led/built/ran/set/cut/won/made/wrote); a bullet with a digit needs a purpose marker (" to ", "so ", " for ",
  "when ", "after ", "enabling", "allowing") ; a bullet without a digit needs a problem marker
  ("when", "found", "mismatch", "slow", "wrong", "without", "gap", "error", "duplicate", "manual", ...)
  ; no "because" / "since" / "due to" / "owing to" (a "causal" problem); ≤ 230 characters;
- page: one verb opens ≤ 2 bullets; one shape covers ≤ ceil(0.4 × bullets); with 6+ bullets at least 3 shapes.
Write cases whose other rules are all clean unless the case is about them, so the expected set is exactly the kinds you list.
