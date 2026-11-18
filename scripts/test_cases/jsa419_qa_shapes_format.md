A JSON object per case: {"name": "...", "entry": {"q": "...", "yes": true|false (optional), "pick": ["/regex/i", ...] (optional), "box": "..." (optional)},
 "label": "<the form question, usually equal to entry.q>", "type": "text" | "select" | "radio" | "checkbox", "options": [...] ([] for text),
 "expect": "<the exact value returned>" | null (null = no answer), "spec_quote": "..."}
Use realistic form wordings (job application forms: consent boxes, work location, years of experience, team / area choices).
Regexes are JavaScript literals with flags; options are the exact strings shown on the form.
