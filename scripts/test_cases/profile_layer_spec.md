# Spec: the candidate profile layer (JSA-077)

Personal facts live in one JSON profile; code reads it. Three behaviours to test.

## 1. resolve — which profile file is used
Candidates in order: (a) the file named by the environment variable JSA_PROFILE, if set AND the file exists;
(b) config/profile.json (the user's own); (c) config/profile.example.json. First existing one wins. None exists → error.
Same idea for data files via data_file(name): config/<name> if it exists, else config/<stem>.example<ext>
(e.g. wd_profile.json → wd_profile.example.json); an env override, when given and set, wins over both (it is not checked for existence).

## 2. get(dotted_key, default) — read a value
"contact.email" walks nested objects. A missing key at any level, or walking into a non-object, returns `default` (None if not given).
A present key whose value is null/false/0/"" returns that value, not the default.

## 3. answer — a form question answered from the profile
The profile has "answers": {rule_id: answer}. An answer may hold: text (string), yes (true/false), pick (list of option
regexes written as "/source/flags", best first), alts, combo, date, note. The rules (in code) only recognise questions:
  first_name  ← "First name"            email ← "Email"           phone ← "Phone number"
  gender      ← "Gender"                 spons_future ← "Will you now or in the future require visa sponsorship?"
  authorized  ← "Are you legally authorized to work in the United States?"
Behaviour:
- Free-text question (no options): value = answer.text; a yes/no rule with no text gives "Yes" / "No".
- Question with options: the first `pick` regex that matches an option wins (options compared trimmed); a yes/no rule picks
  the option starting with "Yes" (or "No").
- A rule whose answer is missing from the profile → status "unknown" (no value).
- profile.work_auth.restricted = true (e.g. a student visa): for `authorized` with options, "Yes, with restrictions" is chosen when
  offered, and an option saying "without restrictions" / "permanent" / "citizen" is never chosen as the Yes.
  restricted = false (e.g. a citizen): the plain Yes option is chosen, including "Yes, without restrictions".
