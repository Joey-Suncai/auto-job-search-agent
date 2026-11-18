# SuccessFactors register form: answering a radio group that has no readable question (JSA-335)

On a SuccessFactors "Create Account" form, some radio groups have no question text the agent can read (Arthrex 2026-11-12:
only the option texts are visible, e.g. "Any Arthrex recruiter worldwide. All recruiters within Arthrex can potentially
see your profile and approach you for other positions." and "Only recruiters in my region ...").

Function `option_answer(options, saved)`:
- `options`: list of the group's option texts (strings; blank or None entries are ignored; surrounding whitespace is ignored).
- `saved`: dict mapping a saved-answer key (e.g. "profile_visibility") to a list of pick patterns. Each pattern is written
  as a JavaScript regex literal string "/<regex>/<flags>", e.g. "/^any\\b.{0,80}\\brecruiters?\\b.{0,30}\\bworldwide\\b/i".
  Flag "i" = case-insensitive. A pattern is tested with a search (not a full match) against the stripped option text.
  A pattern that is not in "/.../flags" form, or does not compile, is ignored. A single string instead of a list is
  treated as a one-pattern list.
- Count every (saved key, option) pair where at least one of that key's patterns matches that option.
- If there is exactly ONE such pair in total, return a 2-element tuple: (the stripped option text,
  "answers.<key>.pick (option content)").
- Otherwise (no matching pair; two or more options matching; two or more saved keys matching; empty options; empty saved)
  return None — the group is then left for the human.
