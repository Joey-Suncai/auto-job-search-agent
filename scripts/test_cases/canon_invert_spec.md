# canon.pick_for(key, label, options) / canon.judge(key, label, value) — JSA-267

Facts: the candidate does NOT need sponsorship now (this internship is on CPT) and WILL need sponsorship in the future.
Canonical fields: `sponsorship_future` accepts an answer starting with "yes" or "(I) (will/would) require(s)/need(s)
(visa/immigration/employer/employment/H-1B) sponsorship", and rejects one that has the word "not", "no" or "never";
`sponsorship_now` accepts an answer starting with "no".

A question is INVERTED when (lower-cased) it has "without" followed within 60 characters by "sponsor", or "do/does/will/
would not need/require" followed within 40 characters by "sponsor". Example: "Are you authorized to work in the U.S.
without the need for sponsorship now or in the future?". An inverted question asks the opposite, so its answer is judged
FLIPPED ("Yes…" ↔ "No…"; an answer starting with neither stays as it is). An inverted question is judged against
`sponsorship_now` when it mentions only now / this internship / this position ("for (the duration of) this|the
internship|position|role|job", "duration of this internship", "now", "currently", "at this time", "today") AND none of
"future", "after graduat", "at any time", "any time after", "later", "eventually", "going forward", "upon graduation",
"full-time"/"full time"; otherwise against the key given.

- `judge(key, label, value)` → (ok, why): not inverted → the plain check of value against key; inverted → the check of
  the flipped value against the chosen key.
- `pick_for(key, label, options)` → the first option (list order; skipping empty ones and ones starting "select one",
  "please select", "--", "choose") that judge() accepts; None when none passes. Not inverted → the plain pick of key
  over the options (an exact accepted text "yes" / "no" first, then the first option that passes).

So: "…without the need for sponsorship now or in the future?" with [Yes, No - I would need sponsorship] →
"No - I would need sponsorship"; "…authorized to work for the duration of this internship without sponsorship?" with
[Yes, No] → "Yes" (judged against sponsorship_now); "Will you now or in the future require sponsorship?" (key
sponsorship_future, not inverted) with [Yes, No] → "Yes".
