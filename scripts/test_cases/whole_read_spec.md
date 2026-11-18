# Whole-question read of rule-answered critical questions (JSA-288) — spec

Before an application is submitted, every form question that a keyword RULE answered and that is CRITICAL gets an
independent read by a language model. The model sees the whole question, its options and the candidate's facts, never
the rule's answer. If the model's answer means the same as the rule's, the answer stays; otherwise (different answer,
the model says UNSURE, or the model call fails) the question is stopped and asked to the human. The model never supplies
an answer of its own.

## select(items, qa) → the items to read (a list, in input order, each item copied with a `group` field added)
Each item: {key, label, options, type, value, rule}.
- An item is read only when the question's class is critical AND its group is one of: work_auth, education, record,
  experience. Use these classes for the test labels:
  - work_auth: any label about sponsorship, visa, work authorization, citizenship, immigration ("Will you require sponsorship?").
  - education: degree, major, GPA, school, graduation ("What is your GPA?", "School", "Discipline").
  - record: criminal conviction / felony questions ("Have you ever been convicted of a felony?").
  - contact (NOT read): name, e-mail, phone, address ("Email", "First Name", "Phone").
  - eeo (NOT read): gender, race, veteran, disability ("Gender", "Are you a protected veteran?").
  - non-critical (NOT read): "How did you hear about us?", "Are you willing to relocate?", salary.
- Never read: a value that is a link (starts with http:// or https://) or longer than 300 characters (an essay); no rule (rule empty or missing); value empty string, null or empty list; item has leave = true; type file,
  hidden or password; rule is one of linkedin, website, full_name, first_name, last_name, email, phone, address, city,
  state, zip, sms, or starts with how_heard.
- rule "qa:N" (a saved answer, entry N of the qa list, 1-based): NOT read when that entry's question `q`, normalised
  (lower case, the word "required" and "*" removed, every run of non-letters/digits/apostrophes → one space, trimmed), is
  equal to the item's label normalised the same way — that is the human's own answer for exactly this question. Read
  otherwise (entry missing, or a different question text that the entry's pattern happened to match).

## same(rule_value, model_value, options) → bool
- model_value null → false. Either side empty → false.
- Values may hold several picks separated by " | " (or be lists): same only when both have the same number of picks and
  every rule pick is the same as some model pick.
- Case, punctuation and spaces do not matter; a trailing bracketed note on either side does not matter
  ("F-1 (CPT)" = "F-1").
- With options: the same when both values name the same option (an exact or prefix match of the option).
- A bare month: names and numbers are the same ("September" = "Sep" = "09" = "9").
- Dates: compared by year and month ("12/2027" = "December 2027" = "2027-12-15" = "12/01/2027"); a bare year ("2027")
  matches any date in that year.
- Numbers: same value ("3.60" = "3.60/4.0" = "3.790").
- Otherwise different ("Bachelor" vs "Master's", "Yes" vs "No", "University of Chicago" vs "Hyde Park").

## gpa_either(label, a, b) → bool (Joey 2026-11-10: a cumulative GPA of 3.60 or "none" are both right)
- true only when the label is a GPA question (contains "GPA", "grade point", "cumulative average/result" or "overall
  result") that does NOT mention "major", AND both a and b are each either 3.60 (also "3.60/4.0", "3.60 / 4") or a
  none-like value: N/A, n/a, NA, none, not applicable, other, no GPA, no GPA yet, not yet available, "-" (case-insensitive).
- a band whose range holds 3.60 ("3.5 - 3.9", "3.70-3.89", "3.5 to 3.9") counts as 3.60 (JSA-288b).
- false for any other value on either side (3.85, 3.81, a band that does not hold 3.60 such as "3.8 - 4.0", empty), for "major GPA" questions, and for
  non-GPA questions.
- In read_items, gpa_either(label, rule value, model answer) true counts like same() (agree).

## month(s) → 1..12 or null; ym(s) → [year, month or null] or null
- month: "September" → 9, "sep." → 9, "09" → 9, "12" → 12, "13" → null, "2027" → null.
- ym: "12/2027" → [2027, 12]; "2027-06-14" → [2027, 6]; "June 14, 2027" → [2027, 6]; "06/14/2027" → [2027, 6];
  "2027" → [2027, null]; "soon" → null.

## enabled(env) → bool
- false when env CX_WHOLE_READ = "0", or JSA_NO_PUSH is set (non-empty), or CX_DATA is set (non-empty).
- otherwise true when CX_WHOLE_READ = "1" or CX_SECOND_OPINION = "1"; else false.

## read_items(items, facts, post) → {key: {agree, how, model}}
Up to three model steps, `post` = the injected model call (it is told which model is asked: "fast" or "strong"):
1. The FAST model answers each question (JSON {"answer": "...", "reason": "..."}). "UNSURE" or an empty answer = no
   answer. same(rule value, fast answer) → agree true, how "same" (no further step for that item).
2. Every other item (fast answer different, no answer, or the call failed) is asked again — the same question — by the
   STRONG model. Its answer decides:
   - same(rule value, strong answer) → agree true, how "confirm".
   - no answer → agree false, how "unsure". The strong call raised an error → agree false, how "error".
   - different answer → agree false, how "disagree".
3. Only for a "disagree" item WITHOUT options: the FAST model judges whether the two answers (rule's and strong's) mean
   the same thing (JSON {"answer": "SAME" or "DIFFERENT"}). SAME → agree true, how "meaning". DIFFERENT → stays
   "disagree". Items with options never get step 3.
Identical prompts to the same model are asked once (a cache).
