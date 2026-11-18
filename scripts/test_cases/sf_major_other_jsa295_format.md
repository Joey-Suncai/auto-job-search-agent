Return {"cases": [...]}. Each case: {"name": str (unique), "fn": "major_choice" | "other_major_box", "input": object, "expect": any,
"spec_quote": str, "ambiguous": false}.
major_choice input {"options": [str], "major": str, "has_box": bool}; expect [str|null, str|null].
other_major_box input {"fields": [{"key": str, "label": str, "type": "text"|"textarea"|"combo"}]}; expect str key or null.
Write about 22 cases: 15 major_choice (majors "Applied Data Science" and "Economics"; lists with and without Other, Computer
Science, Information Systems, placeholders; has_box true and false), 7 other_major_box. Realistic SuccessFactors lists.
