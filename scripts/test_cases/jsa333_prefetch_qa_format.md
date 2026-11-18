A JSON object per case, one of three kinds.

kind "applied": {"name": "...", "kind": "applied", "label": "<question>", "options": ["Yes","No"] or [], "company": "a Greenhouse employer",
 "tracker": [{"company": "a Greenhouse employer", "applied_on": "2026-10-31"}], "today": "2026-11-17", "expect": "yes" | "no" | "ask", "spec_quote": "..."}
- "today" is only for your date arithmetic; the harness uses the real tracker dates relative to today as "days_ago" instead:
  write tracker entries as {"company": "a Greenhouse employer", "days_ago": 17}; do not write applied_on.

kind "ack": {"name": "...", "kind": "ack", "label": "<checkbox label>", "options": ["..."], "expect": "<the option>" | null,
 "spec_quote": "..."}   (expect null = this rule must not answer; some other rule or none may)

kind "overlap_shape": {"name": "...", "kind": "overlap_shape", "table": [<qa entries as {q, match?, text?, yes?, pick?}>],
 "new": {"q": "...", "text": "..."}, "options": ["..."] or [], "expect": {"blocked": true | false},
 "spec_quote": "..."}   (table numbered from 1, the new entry is last; pick = list of JS regex literal strings, text = the plain option)
