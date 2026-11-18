Return JSON: {"cases": [ ... ]} with cases of these shapes (mix all four, ~8 each):
{"fn": "school_pick", "want": "...", "options": ["..."], "alts": ["..."], "expect": "<option>" | null}
{"fn": "major_pick", "major": "...", "prefs": ["..."], "options": ["..."], "expect": "<option>" | null}
{"fn": "degree_pill", "level": "master|bachelor|phd|doctorate|other", "pills": ["..."], "expect": "<pill>" | null}
{"fn": "empty_required_lists", "blocks": [{"title": "...", "required": true, "items": 0, "add": "ADD ..."}], "expect": ["..."]}
Use realistic Oracle lists: several "University of Illinois at …" campuses, "University of Chicago" vs "Chicago State
University", "Other - School Not Listed", majors like Data Science / Data Analytics / Agricultural Economics /
"Other - Field of Study Not Listed", degree pills Associates / Bachelors / Masters / Doctorate / Postdoctorate /
Graduate Diploma.
