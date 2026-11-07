Each case is a JSON object: {"id": "c1", "fn": <one of the functions below>, "input": {...}, "expect": <value>, "spec": "<quoted spec sentence>"}.
Functions (pure, no I/O):
- "track": input {"track": "<store track name>"} → expect the material track string (Data_Analyst | Data_Engineer | Product_Manager | AI_Agentic_Engineer).
- "runner": input {"ats": "<platform string, e.g. ashby, lever, greenhouse, workday, oracle, '' >"} → expect "run_form.py", "run.py", or null when the platform is not in this pipeline.
- "parse": input {"output": "<multi-line runner stdout>"} → expect {"status": "<word>", "secs": <number or null>, "reasons": [<strings>]}.
  reasons = the parts of the LAST "NOT submitted: ..." line after the colon, split on " | " and stripped; [] when there is no such line. With no STATUS line: status "crashed" and reasons = [the last non-empty output line].
- "ready": input {"status": "<word>", "reasons": [..], "output": "<stdout>"} → expect true/false (ready to submit after a dry-run).
- "size": input {"n": <jobs in batch>, "max": <--max value or null>} → expect null when allowed, or the string "too many" when refused.
