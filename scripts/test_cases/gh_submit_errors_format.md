A JSON array of cases: {"name": str, "html": "<a small HTML body with one <form> (inline styles allowed; no scripts)>",
"plan": [{"key": str, "label": str, "sel": "#id or [name=\"…\"]"}], "expect": [{"field": str, "msg": str}], "quote": the spec
sentence it tests}. msg = the message text with whitespace collapsed. Cover: a required file slot with "This field is
required." in a <p class="helper-text helper-text--error"> under it (Greenhouse style, the file input visually hidden), two
fields with errors, a hidden (display:none) error, the legend "* indicates a required field", a label containing
"required", a description "Please select all that apply" (not an error) vs an error-styled description, role="alert",
aria-invalid on a text input in the plan and one not in the plan (id / name fallback), an error outside any plan field's
wrapper with a <label> in its .field wrapper, a wrapper holding two plan fields, a message longer than 160 characters,
no errors at all (expect []), the same field with two messages (listed once).
