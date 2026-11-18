A JSON array of 40 cases of two kinds.
Kind 1: {"name": "<unique snake_case>", "fn": "prompt_queries", "want": "<text>", "expect": [list of strings]}.
Kind 2: {"name": "<unique snake_case>", "fn": "pick_by_prefs", "opts": [strings], "prefs": [strings], "expect": "<option text or null>"}.
Make 18 of kind 1 and 22 of kind 2. Use real Workday Field of Study / Degree / Skills / School options (e.g. "Computer Sciences, Technology, or Business",
"Computer and Information Science", "Management Information Systems", "Python (Programming Language)", "Economics, General"), boundaries
(short first words, blank want, duplicates), preference order (a lower preference never jumps the queue), exact before closest, ties by list order,
"other" preference ignored, preference shorter than 4 characters.
