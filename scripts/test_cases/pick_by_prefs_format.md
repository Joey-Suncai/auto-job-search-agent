Return a JSON array of test cases. Each case:
{"name": "short unique snake_case name", "options": ["Accounting", "Science", ...], "prefs": ["Data Science", ...], "expect": "Computer Science"}
expect is the exact option string, or null for None. Use realistic university major lists (5-15 options).
