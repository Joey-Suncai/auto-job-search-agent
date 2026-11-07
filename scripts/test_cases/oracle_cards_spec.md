# Oracle imported education cards and refused submits (JSA-147, 2026-11-04)

## edu_fill(school, education, today) → dict | None
- `school` = the card's text (may contain the major, the school in capitals, "Fields to fix: 2" …); `education` = list of
  profile entries {school, match_re?, level, end ("YYYY-MM")?, current?, city, state}; `today` = "YYYY-MM-DD".
- The first entry whose `match_re` (a regular expression; if missing, the entry's school name) is found in the card text
  (case-insensitive) is used. None when no entry matches or the card text is empty.
- Result: {"city": entry city, "state": entry state, "graduated": "No" if the entry is `current` or its `end` month is after
  today's month (compare "YYYY-MM" strings), else "Yes" (an entry without end and not current → "Yes"),
  "degree": "Master's" for level master, "Bachelor's" for bachelor, "Doctorate" for phd or doctorate, else None}.

## submit_refused(text) → str
- Returns the matching sentence part (non-empty string) when the page says the submit did not go through:
  "You have N issue(s) that need(s) to be fixed before you can submit", "need to add or modify some info before
  submitting", or "Fields to fix: N" (case-insensitive, any whitespace). Otherwise "" (e.g. a thank-you page, a normal form).

## classify(url, text) — the My Profile page after Submit (Ricoh 11-04)
- A URL containing "/my-profile" whose text has "Applied on <M/D/YYYY>" (one or two digit month and day, two or four digit
  year; case-insensitive) → "done". Without "Applied on <date>" the My Profile page is not "done".

## profile_lists(text, job_id, title) → bool
- True only when the text has "Applied on <date>" (as above) AND either the job id appears as a whole number (not inside a
  longer number: "8491" is in "Careers 8491" but not in "84910") or the title appears (case-insensitive). Otherwise False.
