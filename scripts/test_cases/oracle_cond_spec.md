# Oracle conditional boxes: which ones the runner fills (JSA-174, an employer 2026-11-05)

Oracle application forms show some text boxes only after an earlier answer ("If 'Other' please specify" after a source
question answered Other; "If you indicated F-1 visa … number of months remaining" after a visa-type answer) and ask for
things the shared answer rules answer too eagerly ("Please provide a secondary email." got the primary address). The
runner decides per box with these pure helpers.

## is_secondary_email(label) → bool
- True when the label asks for an e-mail address that is not the main one: the words "secondary", "alternate",
  "alternative", "additional", "second", "backup" or "other" directly before "email" / "e-mail" / "email address"
  (optionally with "a" / "an" before them), e.g. "Please provide a secondary email.", "Alternate Email Address",
  "Second e-mail", "Backup email (optional)", "Other email address". Case-insensitive.
- False for the main address ("Email Address", "Email", "Confirm Email", "Personal email") and for questions that only
  mention e-mail ("May we contact you by email?", "Use email for communication", "Other contact preference").

## is_how_heard(label) → bool
- True for a question about where the candidate learned of the job: "How did you hear about …", "Please indicate how you
  heard about <Company>", "How did you find / learn about this job", "Where did you see / find this posting",
  "Source", "Referral source", "Recruitment source". Case-insensitive. False for other questions ("Have you attended any
  an employer events?", "Did you hear back from a recruiter?", "Open source projects you contributed to").

## box_plan(label, kind, required, rule_answer, related, facts, options) → dict | None
Arguments: `label` (the box's question), `kind` ("text", "textarea", "select", "pills", "radio", "checks", …),
`required` (bool), `rule_answer` (the shared rules' answer: {} or {"status": "ok"|"unknown", "value": …, "rule": …}),
`related` (the nearest earlier choice question on the same page: {"label": str, "answer": str} or null),
`facts` ({"primary_email": str, "secondary_email": str or null, "how_heard_text": str or null}), `options` (list of the
box's own option texts; [] for text boxes).

Result: null = no special case, the shared rules' answer is used as it is. Otherwise
{"action": "fill" | "leave" | "ask", "value": <text or null>, "rule": <name>}; "value" is null unless action is "fill".
The first rule below that applies decides:

1. `rule_answer.rule` starts with "qa:" (the candidate's own saved answer) → null.
2. Secondary e-mail box (`is_secondary_email(label)`), rule "secondary_email":
   - `facts.secondary_email` is a non-empty address that differs (case-insensitive, spaces ignored) from
     `facts.primary_email` → fill with it;
   - else required → ask; else → leave (an optional box stays empty — the main address is never typed twice).
3. "Other" follow-up box (`is_other_followup(label)`: "If 'Other' please specify", "If other, please specify",
   "Other (please specify)", "If you selected Other, please explain", "Please specify"), rule "other_followup":
   - when `related` is null or its answer does not start with the word "Other" / "Others" (case-insensitive, quotes
     ignored; "Other - not listed" counts, "Otherwise" and "Brother" do not) → required → ask, optional → leave;
   - the related answer is Other and `is_how_heard(related.label)`: a text / textarea box → fill with
     `facts.how_heard_text` (ask when that is empty); a box with options → fill with the single option that starts with
     "Other" (ask when there is none or more than one);
   - the related answer is Other but the related question is not a how-heard question (race, visa type, degree …) →
     ask (the candidate's own words are needed).
4. A text / textarea box that asks for a number — the label contains "number of months", "number of years",
   "number of days", "number of weeks", "how many" or "how long" — while `rule_answer` is ok with a value that is not a
   plain number (digits, optionally one decimal point) → ask, rule "number_asked". A plain-number value, an unknown rule
   answer, or a box with options → this rule does not apply.
5. Anything else → null.
