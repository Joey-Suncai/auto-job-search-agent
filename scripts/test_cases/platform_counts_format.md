Each case is one of:
{"name": "...", "fn": "platform_of", "args": {"url": "<string or null>"}, "expect": "<platform or null>", "spec_quote": "...", "ambiguous": false}
{"name": "...", "fn": "row_platform", "args": {"row": {<job row fields>}}, "expect": "<platform or null>", "spec_quote": "...", "ambiguous": false}
{"name": "...", "fn": "summarize", "args": {"rows": [ {<job row>}, ... ]}, "expect": {"<platform>": {"rows": 0, "ok": 0, "ok_ab": 0, "ok_intern": 0, "ok_newgrad": 0, "ab_any": 0}}, "spec_quote": "...", "ambiguous": false}
Use about 12 platform_of cases, 4 row_platform cases and 4 summarize cases.
