A JSON array of cases: {"name": "<unique snake_case>", "cdp": "<endpoint url>", "list_result": <list | object | "unreachable">,
"new_result": "ok" | "unreachable" (only used when a tab must be opened), "expect_return": true|false,
"expect_requests": [["GET", "<url>"], ["PUT", "<url>"]] (in order), "spec_quote": "<spec sentence>"}.
Cover every rule, trailing slash, target types (page, service_worker, background_page, iframe, other), several tabs,
empty list, non-list answers, both failure modes.
