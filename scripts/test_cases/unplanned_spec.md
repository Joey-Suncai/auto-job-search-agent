# Runner.unplanned_required() — spec (Greenhouse runner run.py, 2026-11-03)

Given an application page (HTML, one <form>) and the plan's field list (each with a `key` and a CSS `sel` like "#resume"),
return the ids of the REQUIRED form controls inside a <form> that the plan does not cover, in document order.

- Controls looked at: every input, textarea and select inside a <form>. Skipped: type="hidden", disabled ones, ones
  without an id, ids starting with "country", "react-select" or "iti".
- Required = the `required` attribute, or aria-required="true", or — for a file input only — the text of its nearest
  ancestor element matching ".field, .application-question, div" contains "*" or the word "required" (case-insensitive)
  within its first 200 characters.
- Covered by the plan = the id (with "[]" removed) equals a plan key (with "[]" removed) or a plan selector without its
  leading "#", or starts with such a key followed by "_" or "[]".
- Return the list of uncovered required ids (strings), [] when none.
