A JSON array of 30 cases of two kinds.
Kind 1: {"name": "<unique snake_case>", "fn": "open_unconfirmed", "now": "<ISO time with offset>", "rows": [ {...} ], "days": <int or omitted>, "expect": [<folder names, in the expected order>]}.
Kind 2: {"name": "<unique snake_case>", "fn": "receipt_decision", "at": "<ISO>", "now": "<ISO>", "subject": <string|null>, "hours": <int or omitted>, "expect": "confirm"|"wait"|"joey"}.
Make 18 of kind 1 and 12 of kind 2. Use real-looking folders (2026-11-11_Entrust_AI_Developer_Intern, 2026-11-10_Bosch_Group_Motorsport_Software_and_Data_Analytics_G), ats lever / successfactors / workday, times in -06:00, boundaries (exactly 7 days, exactly 48 h, 47 h 59 min), later submitted row, dry-run rows, bad `at`, empty list.
