A JSON array of cases, one object each, with "fn" naming the function:
{"name": str, "fn": "login_url", "args": [url], "expect": [kind|null, url|null]}
{"name": str, "fn": "field_label", "args": [fid, label], "expect": str}
{"name": str, "fn": "parse_steps", "args": [text], "expect": {"current": int, "total": int, "name": str, "steps": [str]} | null}
{"name": str, "fn": "is_final", "args": [button_text, steps_object_or_null], "expect": true|false}
{"name": str, "fn": "pick_button", "args": [[{"id": str, "text": str}, ...]], "expect": {"id": str, "text": str} | null}
{"name": str, "fn": "classify", "args": [url, text], "expect": str}
Spread the cases over all six functions (at least 4 each), with near misses (icims=10, login.icims.com, "Submit Profile",
"Log in with an employer" before "Submit Profile", a step bar without a Current step, a thank-you text that also shows a step bar).
