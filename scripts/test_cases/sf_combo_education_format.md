Return {"cases": [...]}. Each case: {"name": str, "fn": one of "group_rows" | "row_plan" | "pick_school" | "pick_degree" |
"pick_major" | "companion" | "pick_status" | "rebind", "args": {...}, "expect": ..., "spec_quote": str, "ambiguous": false}.

args and expect per fn (entries are named "A" / "B" — the facts in the spec; the harness supplies them):
- group_rows: args {"fields": [{"key": str, "label": str, "type": "combo"|"text"|"textarea", "value": str}]};
  expect = [[key, key, ...], ...] (one list of keys per row, page order; [] when there is no row).
- row_plan: args {"rows": [{"school": str, "other": str}]}; expect {"rows": {"0": "University of Chicago", ...},
  "delete": [int], "add": [str], "unmatched": [int]} (school names exactly as in the facts).
- pick_school: args {"options": [str], "entry": "A"|"B"}; expect [option or null, "match"|"other"|null].
- pick_degree: args {"options": [str], "entry": "A"|"B"}; expect option or null.
- pick_major: args {"options": [str], "major": str}; expect option or null.
- companion: args {"fields": [{"key": str, "label": str, "type": "combo"|"text"|"textarea"}]} (the boxes of one row);
  expect key or null.
- pick_status: args {"options": [str], "entry": "A"|"B"}; expect option or null (today = 2026-11).
- rebind: args {"row": {"key": str, "label": str}, "fields": [{"key": str, "label": str}], "taken": [str]};
  expect key or null.

Write 24 cases: group_rows 4, row_plan 5, pick_school 4, pick_degree 2, pick_major 3, companion 2, pick_status 2,
rebind 2. Include: three parser rows of which one is extra, rows with "No Selection", a school missing from the list
(options with and without "Other"), "Loyola University Chicago" as a near miss, "There were no results" as the only
option, Majors lists without any data-science option, a row followed by an unrelated long question, three boxes
labelled "School" in rebind.
