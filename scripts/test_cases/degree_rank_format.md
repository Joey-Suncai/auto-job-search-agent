Return a JSON array of test cases. Each case:
{"name": "short unique snake_case name", "options": ["Bachelor's Degree", "MS-Law", "Master of Science", ...], "expect": "Master of Science"}
expect = the exact option or null. Include bachelor/associate/doctorate options as distractors (never chosen).
