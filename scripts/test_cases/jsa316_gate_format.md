Each case: {"name": "...", "label": "<question label>", "value": "<the answer on the form>",
 "expect_class": "critical:defense" | "critical:eeo" | "critical:other" | "non-critical" | "any",
 "expect_gate": "pass" | "block:defense", "spec_quote": "...", "ambiguous": false}
Use "any" for expect_class when the spec does not fix the class.
