# Reading a Greenhouse form's validation errors after Submit — spec (JSA-209, 2026-11-05)

`submit_errors(plan_fields)` runs in the page and returns the visible validation errors of the application form, so the
runner can tell "the form refused the submit (field X: This field is required)" from "submitted, no confirmation seen".
Returns a list of {"field": str, "msg": str}, in document order, each field at most once (its first message).

Scope: the first <form> on the page (the whole body when there is none).

## Error messages
An element counts as an error message when ALL hold:
- it has no child elements, its text (whitespace collapsed, trimmed) is non-empty and at most 160 characters, and it is
  visible (not display:none / visibility:hidden, has a non-zero size);
- its text matches the error pattern (case-insensitive): "this field is required", text ending in "is required" (an
  optional final "."), "please enter / select / fill / provide / complete / upload / attach", "is invalid",
  "invalid email / phone / format / value", "can't be blank", "cannot be blank" — OR it is error-styled (its own class or
  its parent's class contains "error" or "invalid", or it has role="alert");
- its text is not the legend ("indicates a required field", "required fields are marked");
- it is not inside a <label>, unless its own class contains error, invalid or helper (a label that says "Email *
  required" is not an error);
- it is not inside a description container (id ending in "-description", class "question-description", or a class
  containing "description") unless it is error-styled.

## Field name of a message
Walk up from the message element through its ancestors (stop at the form). At the first ancestor that contains exactly
one control (input / textarea / select, hidden ones included) matched by a plan field, the field is that plan field's
label. A control matches a plan field when its id or its name equals the plan field's key, or it matches the plan field's
CSS selector `sel`. An ancestor that contains controls of two or more plan fields ends the walk without a match.
Without a match: the text of the first <label> in the message's closest ancestor matching
`[class*="field"], .application-question, fieldset, li`; without one, the message text itself.

## Invalid controls
Also every visible control with aria-invalid="true": field = the label of the plan field it matches, else its id, else its
name; msg = "aria-invalid". Listed after the messages; a field already listed is not repeated.
