A JSON array of 16 cases: {"name": str, "fn": "consent_approved", "args": [text, cli, approved_list], "expect": true|false}.
Cover: profile match, cli match, neither, case / whitespace differences (newlines, double spaces), empty cli with empty
snippets (false), null items, plain-string items, snippet longer than the text, partial-word overlaps.
