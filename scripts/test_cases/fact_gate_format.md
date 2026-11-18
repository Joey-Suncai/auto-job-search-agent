Each case: {"name": "...", "label": "<question label>", "value": "<the answer on the form>", "type": "text"|"select"|"radio"|"checkbox"|"date",
 "options": [...] (may be empty), "source": "rules:…" | "answers.json" | "deepseek" | "",
 "expect": "pass" | "block:<kind>" (kind one of conviction, any_employer, degree_level, major, start_date, pattern, qa),
 "spec_quote": "...", "ambiguous": false}
