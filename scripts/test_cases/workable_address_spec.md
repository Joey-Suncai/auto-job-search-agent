# Workable single address box (JSA-146, 2026-11-04)
full_address(fields, ans, city_state_zip) → answers.
- `fields`: the form's fields [{key, label}]; `ans`: {field key: {status, value, …}}; city_state_zip e.g. "Chicago, IL 62701".
- Only the `address` answer can change. It becomes "<street>, <city_state_zip>" when ALL hold: ans["address"].status is
  "ok"; city_state_zip is non-empty; no OTHER field (key other than "address") has a label with the word city, zip,
  postal or state, or a key "city", "zip" or "state"; the street value is non-empty; and the street does not already
  contain the city (the part of city_state_zip before the first comma, case-insensitive).
- Otherwise the answers are returned unchanged. Other answers are never changed.
