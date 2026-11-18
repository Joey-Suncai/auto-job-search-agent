Return JSON: {"cases": [ ... ]}. Each case is one of:
{"fn": "whole_label", "label": "<plan label>", "text": "<label text on the page>", "expect": true|false, "why": "<short>"}
{"fn": "value_check", "type": "select|radio|multi|text|textarea|combo|date", "options": ["..."], "answer": "<answer>", "expect": "ok"|"stop", "why": "<short>"}
Mix both functions (about half each). Include the Ashby EEO example: an EEO "Gender" field with options Male / Female /
Decline to self-identify, and a custom "What is your gender identity?" question with options Man / Woman / Non-Binary.
Use non-breaking spaces (write them as   in JSON), new lines, trailing "*", case differences, multi answers with
" | ", and near-miss options.
