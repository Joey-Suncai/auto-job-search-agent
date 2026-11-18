A JSON array of 22 cases: {"name": "<unique snake_case>", "ans": null | ["yes", true|false] | ["text", "..."] | ["pick", ["/.../i", ...]] | ["key", "..."],
"live": "<live planned answer, may be empty>", "expect": "agree|differ|layer_asks|live_asks|both_ask|cannot_compare"}.
Cover every kind, yes/no sentences in both directions, "I do not" vs "I do", trailing periods, case, pick patterns that do and
do not match, and empty live answers.
