A JSON array of 18 cases: {"name": "<unique snake_case>", "ds": reading, "hk": reading (may carry "error": true),
"facts": {"<key>": {"yes": true|false} and/or {"text": "..."} and/or {"pick": ["..."]}}, "expect_asks": true|false}.
A reading is {"fact_key": "...", "shape": "...", "negated": true|false, "subject": "...", "confidence": "high|low"} (negated may be left out).
Cover: same key; different keys with the same yes; different keys with opposite yes; one negated making them equal;
one negated making them differ; same text different keys; different text; pick lists equal / different; a key missing
from facts (same key vs different key); yes fact read with shape fill vs yes_no; ds asks; hk asks; hk error; subject other_person.
