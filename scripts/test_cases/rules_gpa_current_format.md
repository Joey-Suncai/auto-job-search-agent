Each case:
{"name": "...", "label": "<the question as the form shows it>", "type": "text" | "textarea" | "select", "options": ["..."] (only for select, else []), "expect": "N/A" | "GPA_ON_FILE" | "<the exact option to pick>" | "none", "spec_quote": "...", "ambiguous": false}
About 10 text / textarea cases (rule 1 wordings, rule 2 exceptions, rule 3 including GPA-before-current) and 6 select
cases (options with "N/A", "NA", "Not Applicable", "Other", and one list with none of them → "none"). Do not use GPA
band lists for rule-3 questions (expect GPA_ON_FILE only for text / textarea).
