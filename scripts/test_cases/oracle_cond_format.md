A JSON array of cases: {"name": "<unique snake_case>", "fn": "is_secondary_email" | "is_how_heard" | "box_plan",
"args": [positional arguments in the spec's order], "expect": <return value>, "spec_quote": "<spec sentence>",
"ambiguous": false}. is_secondary_email / is_how_heard take [label] and return a boolean. box_plan takes
[label, kind, required, rule_answer, related, facts, options] and returns null or {"action", "value", "rule"} exactly
(value null unless action is "fill"). Write 28 cases: is_secondary_email 6, is_how_heard 4, box_plan 18 (qa answer wins,
secondary e-mail with / without / same-as-primary profile address and required / optional, Other follow-up with related
null / not Other / "Otherwise" / Other from a how-heard text box / how-heard list with one and with two Other options /
missing how_heard_text / Other from a race question, number question with a non-number / a number / unknown rule answer /
a select box, and ordinary boxes that must return null).
