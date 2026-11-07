Return {"cases": [...]}. Each case is one call of one helper:
{"name": str (unique), "fn": "option_text" | "radio_selector" | "page_kind" | "accept_link" | "privacy_accepted" | "account_ok",
 "args": {...}, "expect": ..., "spec_quote": str, "ambiguous": false}

- option_text: args {"c": {...}}; expect a string.
- radio_selector: args {"opt": {...}}; expect [selector string, nth number] or null.
- page_kind: args {"sig": {...}}; expect one of "application", "register_apply", "register", "sign_in", "unknown".
- accept_link: args {"text": str}; expect true / false.
- privacy_accepted: args {"text": str, "dpcs_value": str}; expect true / false.
- account_ok: args {"key": str, "want": str, "got": str}; expect true / false.

Write about 5 option_text, 4 radio_selector, 4 page_kind, 5 accept_link, 5 privacy_accepted and 4 account_ok cases:
realistic SuccessFactors texts (e.g. "Make My Profile Visible to" options such as "Any Acme recruiter worldwide (Selecting
this option will enable us to contact you …)"), near misses, order of precedence, length limits, escaping.
