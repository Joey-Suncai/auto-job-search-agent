{"name": "...", "label": "<field label>", "type": "text" | "textarea" | "select" | "checkbox" | "file", "options": [] or ["..."],
 "cover": "<cover.txt text, may be empty>", "expect": {"value": "<exact text typed>" } | {"leave": true} | {"rule_not": "hiring_manager_note"},
 "spec_quote": "..."}
- expect.value = the exact answer; expect.leave = box left empty; rule_not = this rule must not answer.
