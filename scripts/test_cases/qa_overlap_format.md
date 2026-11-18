A JSON object per case, one of two kinds.

kind "overlap" (saving a new entry; the table has no exact duplicates of the new q):
{"name": "...", "kind": "overlap",
 "input": {"table": [{"q": "Salutation", "match": "/^(salutation|prefix)\\b/i", "text": "Mr."}],
           "new": {"q": "Salutation or title", "text": "Mr."}},
 "expect": {"blocked": true, "catches_it": [1], "it_catches": []},
 "spec_quote": "..."}
- table entries are numbered from 1; the new entry gets number len(table)+1. catches_it / it_catches = sorted entry numbers.

kind "answer" (answering one field from a table):
{"name": "...", "kind": "answer",
 "input": {"table": [{"q": "Current school", "pick": ["/^University of Illinois$/i"], "text": "University of Illinois"},
                     {"q": "Current school or university", "match": "/current school/i", "pick": ["/^University of Chicago$/i"], "text": "University of Chicago"}],
           "label": "Current school or university:", "type": "select", "options": ["University of Chicago", "Other"]},
 "expect": {"status": "ok", "value": "University of Chicago", "rule": "qa:2"},
 "spec_quote": "..."}
- type is "select", "radio", "checkbox" or "text" (text = no options). expect is null when no entry catches the label;
  for a miss give status "unknown" and the rule of the newest catching entry, no value.
- Regexes are JSON strings of JavaScript regex literals; escape backslashes.
