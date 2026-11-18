# role_library — specification of the pure functions (for writing test cases; you do not see the code)

## matcher(term) → does a term appear in a text?
- A term is a string, or {"t": "<string>", "cs": true} for a case-sensitive term.
- Plain strings match case-insensitively; "cs": true terms match only with the exact case.
- The term must stand as a whole token: the character before it must not be a letter, digit, underscore, "&", "+" or "/";
  the character after it must not be a letter, digit, underscore, "&" or "+". Examples: "SQL" matches "SQL," and "(SQL)"
  but not "NoSQL" or "SQLite"; {"t":"R","cs":true} matches "Python or R." but not "R&D", "React", "r" or "/R"; "ML" does not match "HTML".
  "A/B testing" matches "A/B testing" (the slash is inside the term).

## split_req(text) → (required part, preferred part)
- The text is split at the FIRST occurrence (case-insensitive, whole word) of any of: preferred, nice to have, nice-to-have,
  nice to haves, bonus, bonus point(s), a plus, pluses, desired, desirable.
- Required part = everything before that word; preferred part = from that word to the end. No marker → (whole text, "").

## stats(texts, lexicon) → competencies and top keywords
A lexicon = competencies, each a list of keyword groups; a group = [canonical term, synonym, synonym, …]. A group "hits" a
JD when any of its terms matches (rules above).
- Keyword df = (number of JDs where the group hits anywhere) / (number of JDs), rounded to 3 decimals.
- Keyword req_share = (JDs where it hits in the required part) / (JDs where it hits anywhere); 0 when it never hits.
- Competency df = share of JDs where ANY of its groups hits; competency req_share = share of those JDs where a hit is in
  the required part.
- Competency score = df × (0.5 + 0.5 × req_share) when df ≥ 0.05, else 0. Weight = score / sum of all scores (4 decimals).
  When every score is 0, every weight is 0.
- Competencies are sorted by weight descending.

## select(jobs, texts, selector) → sorted list of JD ids
- jobs: list of {"id", "track", "title", optional "dup_of"}; texts: {id: JD text}.
- A job is chosen only if its id has a text and it has no (truthy) dup_of.
- Chosen when its track is in selector.tracks; OR, when selector has or_tracks_with_text = {"tracks": [...], "regex": "...", "min_hits": N},
  its track is in those tracks AND the regex (case-insensitive) matches its text at least N times (non-overlapping matches).
- If selector has title_regex, a chosen job must also match it in its title (case-insensitive).
- Result: unique ids, sorted ascending.
