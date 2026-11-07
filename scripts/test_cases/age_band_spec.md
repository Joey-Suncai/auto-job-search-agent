# ageBand(options, age) — spec (2026-11-03)

An application form asks for an age range (EEO-style demographic question). `options` is the list of choice texts as
shown on the form; `age` is a whole number. Return the FIRST option (exact original text) whose numeric band contains
`age`; return "" (empty string) when no option's band contains it (options with no numbers, such as "Choose not to
identify" or "Prefer not to say", are never picked).

Band forms (case-insensitive, spaces may vary, the dash may be -, – or —):
- "A-B", "A – B", "A to B" (e.g. "21-29", "25 to 34", "Age 18–24") → A ≤ age ≤ B.
- "under N", "younger than N", "below N", "less than N" → age ≤ N − 1.
- "N or younger", "N and under", "N or under", "N or less", "N and below" → age ≤ N.
- "N+", "N or older", "N or over", "N and older", "N and over", "N and up", "N or above", "N plus" → age ≥ N.
- "over N", "older than N", "above N" → age ≥ N + 1.
The first matching form in the order above decides an option's band.
