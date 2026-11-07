A JSON array of 30 cases: {"name": "<unique snake_case>", "fn": "<function name>", "args": [positional arguments], "expect": <return value>}.
parse_posting returns {"host","lang","site","job"} or null; classify returns one of the listed state strings; is_final /
geo_same / is_other_followup / same return booleans; pick_option / geo_pick return the option string or null;
email_consent returns "tick" or "ask". Spread the cases over all 11 functions (2–4 each), with edge cases.
