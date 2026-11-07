Return {"cases": [...]}. Each case is one call of one helper:
{"name": str (unique), "fn": "pw_limits" | "pick_password" | "privacy_link" | "radio_question",
 "args": {...}, "expect": ..., "spec_quote": str, "ambiguous": false}

- pw_limits: args {"text": str}; expect [min, max] with numbers or null.
- pick_password: args {"text": str, "items": [[name, password], ...]}; expect [name, password] or null. Use made-up
  passwords of clear lengths (e.g. "Aa1!" repeated) and write their length in the case name.
- privacy_link: args {"text": str}; expect true / false.
- radio_question: args {"texts": [str, ...], "options": [str, ...]}; expect a string.

Write about 8 pw_limits, 6 pick_password, 6 privacy_link and 6 radio_question cases: realistic SuccessFactors page texts
(password hints with other rules such as uppercase / digit / special character, e-mail and name labels around them), near
misses, both bounds inclusive, nothing fits, empty passwords, option texts inside the container text.
