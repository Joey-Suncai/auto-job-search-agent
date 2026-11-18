JSON list of cases: {"name": str, "fn": "receipt_plan" | "unconfirmed_action", "args": [...], "expect": "joey"|"wait"|"pending", "spec": "<spec sentence>"}.
receipt_plan args: [mail_wait (int|null), captcha_seen (bool)]. unconfirmed_action args: [result (dict)].
