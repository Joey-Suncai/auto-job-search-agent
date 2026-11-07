JSON array of objects:
{"name": "short_snake_case_id", "label": "the question label as the form shows it", "type": "select" | "radio" | "text",
 "options": ["option 1", ...] (empty list for a text box),
 "expect": "the exact option text that must be picked (or \"Mobile\" for a text box), or \"UNKNOWN\" when rule 5 applies",
 "why": "spec rule quoted"}
