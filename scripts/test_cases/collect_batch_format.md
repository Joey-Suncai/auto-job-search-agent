Return {"cases": [...]}; each case is one of:
{"name": "<unique>", "fn": "parse_unknown", "input": "<line>", "expect": ["<question>", ["<option>", ...]]}
{"name": "<unique>", "fn": "qnorm_same", "a": "<question>", "b": "<question>", "expect": true|false}
{"name": "<unique>", "fn": "merge", "items": [{"folder": "...", "question": "...", "options": [...], "type": "..."}],
 "expect": {"entries": [{"question_key_of": "<one of the questions>", "folders": [...], "options": [...], "kind": "fact"|"essay"}], "human": <int>}}
{"name": "<unique>", "fn": "qa_args", "entry": {"question": "...", "options": [...], "answer": {...} | null}, "source": "...", "expect": [...] | null}
Write ~24 cases across all four.
