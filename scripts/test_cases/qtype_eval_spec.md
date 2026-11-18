# Scoring a model's reading of a form question (JSA-361)

A model reads a form question into a **reading**: `shape` (fill, yes_no, choice, multi_choice, paragraph, subscription,
data_consent, attestation, file, trap, unclear), `subject` (self, other_person, company, unclear), `time`, `degree`
(current, bachelor, master, highest_completed, after_graduation, none), `topic`, `fact_key` (a fact name such as
spons_now, spons_future, citizen_pr, first_name, marketing, data_consent, referral, references, or "none" / "unknown"),
`negated` (true when YES means the fact is FALSE) and `confidence` (high / low). The scorer compares a reading with the
**gold** reading and decides one outcome.

## When a reading means "ask the user"
A reading means ask when any of these holds:
- fact_key is "none" or "unknown";
- confidence is "low";
- shape is "unclear" or "trap";
- subject is "unclear";
- fact_key is spons_now or spons_future and time is "none" (no time word: Joey 2026-11-16);
- subject is "other_person" and the fact_key is not one of the keys about other people: referral, references,
  relatives, relative_names, know_employee, contact_employer.

## Set 1 — questions the old rules answered wrong (outcome: right / ask / wrong)
Gold gives a list of acceptable `keys`, a list of acceptable `shape`s, a list of acceptable `subject`s, `negated`
(true / false, or null = not checked) and `degree` (a list, or null = not checked).
- A reading that means ask → **right** when gold keys contain "none" (asking is the right outcome there), else **ask**.
- Otherwise the reading is **right** only when ALL hold: fact_key is in gold keys; shape is in gold shapes; subject is in
  gold subjects; negated equals gold negated (when gold negated is not null; a missing negated counts as false);
  degree is in gold degree (when gold degree is not null). Anything else → **wrong**.

## Set 2 — questions the old rules answered right (outcome: same / ask / new_wrong)
Gold gives the fact key that gave the right answer (`key`), the right `answer` text, and `box` (true when the question has no options and is a text box). `facts` maps a fact key to its
value: `{"yes": true|false}` for a yes/no fact, `{"text": "..."}` for a value (either may be present).
- A reading that means ask → **ask** (not an error; it only costs the user a question).
- Shape "paragraph" with a fact whose value has only "yes" (no "text") → **ask**.
- Shape "yes_no" with a fact whose value has no "yes" (a value fact), on a question that is a **box** (gold `box` = true:
  no options, a text control) → **new_wrong** (a yes/no answer in a value box). Without `box` this rule does not apply.
- If the right answer is a yes / no word (yes, no, y, n, true, false — any case), and the reading's fact has a "yes"
  value: the reading's answer is yes when (fact yes) XOR (negated); **same** when that equals the right answer, else
  **new_wrong**. A reading's fact with no "yes" value against a yes / no answer → **new_wrong**.
- Otherwise (a value answer): **same** when the reading's fact_key equals the gold key, or both facts have the same
  "text" (ignore case and surrounding spaces) and the same "yes"; else **new_wrong**.
- A reading's fact_key that is missing from facts and differs from the gold key → **new_wrong**.

Examples of real questions: "Will you now or in the future require sponsorship?" (gold spons_future),
"Will you require immigration sponsorship to begin working for a Greenhouse employer?" (gold spons_now), "Are you legally authorized to
work in the United States without (now or in the future) requiring any visa sponsorship?" (gold spons_future, negated),
"Consent: marketing" (gold marketing, shape subscription), "What is the full name of your referrer?" (gold referral,
subject other_person), "Tell us about a time you taught yourself something difficult" (gold none → ask is right).
