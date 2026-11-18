# Combining several readings of one form question (JSA-361 v2)

A model reads a form question into a **reading** with fields `fact_key`, `shape`, `negated` (true/false; missing = false),
`subject`, `confidence` (high / low) and others. A reading **asks** the user when fact_key is "none" or "unknown",
confidence is "low", shape is "unclear" or "trap", subject is "unclear", or subject is "other_person" with a fact_key
not in: referral, references, relatives, relative_names, know_employee, contact_employer.

## Majority of N DeepSeek readings
The same question is read N times (usually 3). Two readings **agree** when fact_key, shape, negated and subject are all
equal (a missing negated counts as false). With a threshold `agree` (2 = majority of 3, 3 = all three):
- the largest group of agreeing readings has at least `agree` members → the result is that group's reading
  (it keeps its own confidence, so a group of low-confidence readings still asks);
- otherwise → the result asks (confidence low): the readings disagree.
Readings that ask can win the vote like any other (three "unknown" readings → the result asks).

## Haiku re-read of a critical question
For a critical question, a second model (Haiku) reads it once, independently. Combine the DeepSeek majority result `ds`
with the Haiku reading `hk`:
- ds asks → the result is ds (asks);
- Haiku failed (hk has "error": true) → the result asks;
- hk asks, or hk differs from ds in fact_key, shape or negated → the result asks;
- otherwise (same fact_key, shape and negated; subject may differ) → the result is ds (it does not ask).
