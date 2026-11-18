Return {"cases": [...]}. Each case: {"name": str (unique), "fn": "label_key" | "other_school_box" | "question_label" | "school_other_ok",
"input": object, "expect": any, "spec_quote": str, "ambiguous": false}.
input shapes: label_key → {"label": str}; expect = str.
other_school_box → {"fields": [{"key": str, "label": str, "type": "text"|"textarea"|"combo"}]}; expect = str key or null.
question_label → {"label": str, "rows": [str], "kind": "checkbox"|"text"|"combo"}; expect = str.
school_other_ok → {"records": [{"label": str, "value": str}]}; expect = [str labels rejected] (order as in input).
Write about 28 cases: 9 label_key, 6 other_school_box, 7 question_label, 6 school_other_ok. Use realistic SuccessFactors labels.
