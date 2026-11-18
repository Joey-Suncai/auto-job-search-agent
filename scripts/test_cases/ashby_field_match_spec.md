# Spec: choose the right form field and refuse a value that is not in its options (JSA-323)

Two pure functions are tested.

## 1. whole_label(label, text) -> bool
`text` is the text of one label element on an application form. `label` is the question label the plan holds.
True only when `text` IS the whole label:
- case-insensitive;
- any run of whitespace (spaces, non-breaking spaces, tabs, new lines) equals one space;
- leading / trailing whitespace ignored;
- one trailing required marker "*" (with or without a space before it) is allowed.
Anything else is False: `text` that only contains the label ("Gender" inside "What is your gender identity?"),
a label that only contains `text`, an extra word, a different punctuation mark, a missing word.

## 2. value_check(type, options, answer) -> "ok" | "stop"
A form field of `type` ("select", "radio", "multi", or another type such as "text", "textarea", "combo", "date")
with its own list of `options` (may be empty) and the planned `answer`.
- Types other than select / radio / multi → "ok" (no check).
- An empty option list → "ok" (nothing to check against).
- select / radio: "ok" only when the answer equals one of the options, case-insensitive, whitespace runs equal one
  space, leading/trailing whitespace ignored. Otherwise "stop". A synonym is NOT the same option ("Man" is not "Male",
  "Yes" is not "Yes, I am"), and a partial option is not the option.
- multi: the answer is several options joined by " | ". "ok" only when EVERY part (trimmed) is one of the options
  under the same comparison; one part missing → "stop".
