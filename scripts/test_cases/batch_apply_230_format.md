Each case is a JSON object: {"id": "d1", "fn": <one of the functions below>, "input": {...}, "expect": <value>, "spec": "<quoted spec sentence>"}.
Functions (pure, no I/O):
- "runner": input {"ats": "<platform>"} → expect the runner script file name or null.
- "platform": input {"url": "<posting URL>"} → expect the platform string ('' when unknown).
- "command": input {"ats": "<platform>", "folder": "/x/F", "submit": true|false, "ds_ok": true|false} → expect the argv list after the python executable (script name first), or null.
- "size": input {"n": <jobs>, "max": <int or null>, "login": true|false} → expect null when allowed, "too many" when refused.
- "folder_name": input {"date": "2026-11-06", "company": "...", "title": "..."} → expect the folder name string.
- "split": input {"jobs": [{"id","url"}...]} → expect {"gal": [ids], "wd": [ids], "own": [ids], "none": [ids]} (ids in batch order).
- "merge": input {"stdout": {"status","secs","reasons"}, "results": <results.jsonl line object or null>} → expect {"status","secs","reasons"}.
- "parse": input {"output": "<runner stdout>"} → expect {"status","secs","reasons"}.
- "ready": input {"status","reasons","output"} → expect true/false.
