JSON list of cases: {"name": str, "fn": "edu_same" | "edu_select_values", "args": [...], "expect": <bool | list of str>, "spec": "<spec sentence>"}.
edu_same args: [want (JSON string of a list of one entry dict), got (JSON string of an object)]. expect: true/false.
edu_select_values args: [ent (dict), n_selects (int), excluded (list of str)]. expect: list of str.
