Return a JSON array. Each case:
{"name": "snake_case",
 "html": "<full HTML snippet as a JSON string — use &quot; inside value=\"…\" exactly like the spec>",
 "country": "United States" | "Canada" | null,     (the answer given to candidate-location; null = no answer)
 "expect_fields": [{"key": "...", "type": "...", "label": "...", "options": ["..."], "required": false, "survey_for": "*" | "US" | null}],
       (= lever_survey(html), in order; survey_for null for candidate-location)
 "expect_plan_keys": ["candidate-location", "surveysResponses[...][responses][field0]", ...]}
       (= the keys of those fields that stay in the plan after build with that country answer, in order)
Survey ids: short lowercase hex strings. Vary: no select, one all-locations section, a US-only and a CA-only section,
several fields per template, all five field types, a broken JSON template, a select with only the placeholder.
