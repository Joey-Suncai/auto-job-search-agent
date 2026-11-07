Each case is one of:
{"name": "...", "fn": "platform_of", "args": {"url": "<string or null>"}, "expect": "<platform or null>", "spec_quote": "...", "ambiguous": false}
{"name": "...", "fn": "row_platform", "args": {"row": {<job row fields>}}, "expect": "<platform or null>", "spec_quote": "...", "ambiguous": false}
Test the section "SuccessFactors career sites on a company's own domain (JSA-170)" and how it interacts with the suffix
table and row_platform: about 20 platform_of cases (query rule, path rule, digit-count edges, segment counts, trailing
slash, case, Built In exception, suffix match winning) and 4 row_platform cases.
