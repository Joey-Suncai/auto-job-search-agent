# Spec: JSA-354 — "which languages do you speak" questions list ALL the candidate's languages

Candidate profile: languages: [{"name": "Chinese (Mandarin)", "re": "chinese|mandarin", "level": "native"},
{"name": "English", "re": "english", "level": "professional"}]. These rules apply only when no other rule and no saved
answer answers the question. Questions about programming / coding / code / software / scripting languages are never
answered by this rule (status stays whatever the other rules give; here: not "ok" with a language).

## A. Option lists (multi / checkbox, or a plural label) — existing behaviour, must stay
At least two options name a language and no option is a level code (A1..C2). For each profile language, in profile order,
pick the option that starts with it, else the first option containing it; answer = picks joined by " | ".
A profile language with no matching option is simply not picked (never invent an option). E.g. label "Languages Spoken",
type multi, options Spanish / French / Mandarin / Other → "Mandarin" (English has no option; "Other" is NOT picked).
Options English / Mandarin / Spanish → "Mandarin | English".

## B. Text box listing the spoken languages (NEW)
A field with no options and type text or textarea, whose label asks which languages the candidate speaks / knows /
is fluent in (the label contains "language" or "languages" or "language(s)" AND one of: spoken, speak, speaks, fluent,
know, list) answers with every profile language NAME, in profile order, joined by ", ":
"Chinese (Mandarin), English".
- If the label says "other than English" (or "besides English", "apart from English"), leave out English:
  "Chinese (Mandarin)". The same for another named profile language.
- Not answered by this rule (status unknown or no answer — NOT "ok" with a language list): labels with "preferred",
  "proficiency", "level", "rate", "native language", "first language", "primary language", "mother tongue",
  labels that name no spoken/speak/fluent/know/list word (e.g. "Additional Information For Languages",
  "Languages"), and programming / coding language questions ("What coding language(s) are you proficient in?").
- A single yes/no style question that names one language ("Do you speak Mandarin?") is not a list: not answered here.
- Only the PLURAL forms ("languages", "language(s)") count: a singular label such as "I am fluent in this language."
  or "Which language do you speak at home?" is not a list question and is not answered by this rule
  (real Elanco form, 2026-11-01: that statement label must stay unanswered).
- "other than / besides / apart from / excluding / except" leaves out EVERY profile language named after the marker
  ("other than English and Chinese" → nothing left → not answered); a language not in the profile after the marker
  excludes nothing. "natively" / "native" anywhere in the label → not answered (English is never native).
