# Spec: the major / "Area of Study" list in an education row (Joey 2026-11-11, JSA-295)

Two pure functions; each case names one in "fn".

A. major_choice(options, major, has_box) → [option, how] for a dropdown of majors.
   1. An option equal to the major (case-insensitive) → [that option, "match"].
   2. Else an option of 2+ words whose words all appear in the major ("Data Science" for "Applied Data Science"), or an
      option that contains the whole major as words → [it, "match"].
   3. Else, when has_box is true (the row has an "If other, enter Area of Study" text box) → the option that is exactly
      "Other" (case / spaces ignored) → [that option, "other"]; no such option → [null, null]. Never Computer Science here.
   4. Else (has_box false) the fallback, in order: "Computer Science"; then "Information Systems" / "Information System" /
      "Computer Information Systems" / "Management Information Systems"; then "Other" → [it, "fallback"]; none → [null, null].
   Placeholder options ("No Selection", "Select", "Please select", "--") are never picked.
   Note: single-word options such as "Science" or "Data" are NOT a rule-2 match (2+ words needed) unless equal to the major.
B. other_major_box(fields) → the key of the row's text box for a major not in the list: type "text" or "textarea", label
   says other / not listed / specify AND names area of study / major / field of study / subject / discipline / course of
   study. A box for the school ("If other, enter School / Institution Name") is not it. A combo never counts. None → null.
