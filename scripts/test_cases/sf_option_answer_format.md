Each case is a JSON object:
{"name": "<short_snake_case>", "fn": "option_answer",
 "args": {"options": [<strings or null>], "saved": {"<key>": [<pattern strings>] or "<pattern string>"}},
 "expect": null  OR  ["<option text>", "answers.<key>.pick (option content)"],
 "spec_quote": "<the spec sentence>", "ambiguous": false}
Patterns are JSON strings, so a regex backslash is written "\\b" in JSON.
Use the real pattern "/^any\\b.{0,80}\\brecruiters?\\b.{0,30}\\bworldwide\\b/i" in several cases, with realistic option texts.
