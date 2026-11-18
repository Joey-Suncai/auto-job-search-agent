A JSON array of cases, three kinds:
{"name": str, "fn": "posting_url", "job": {...} or null, "expect": str}
{"name": str, "fn": "platform", "url": str or null, "expect": str}
{"name": str, "fn": "lever_parse", "url": str, "expect": [site, uuid] or null}
About 8 posting_url, 14 platform (cover the SuccessFactors region-prefix rule and its limits), 6 lever_parse.
