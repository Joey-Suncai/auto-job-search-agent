# JSA-273 — run_wd.unplanned_fields(planned_keys, fields) → list of labels (pure)
`planned_keys` is a set of field keys the page plan saw, or None. `fields` is the list of field dicts on the page now
(each has "key", "label", "type"). Return the labels of fields whose key is NOT in planned_keys, in the order of `fields`,
skipping fields of type "file" and fields whose label is empty or only whitespace. planned_keys None → [] (no plan known).
An empty planned_keys set means nothing was planned, so every qualifying field is returned. fields None or [] → [].
Labels are returned as given (not trimmed). Duplicate labels with different keys are each returned.
