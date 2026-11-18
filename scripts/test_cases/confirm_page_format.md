Return {"cases": [...]}. Each case: {"name": str (unique, short), "before": {"url": str, "text": str, "form": true|false|null},
"after": {"url": str, "text": str, "form": true|false|null}, "expect": true|false, "spec_quote": str, "ambiguous": false}.
Write 30 cases: the incident and its variants (greeting on the form, spinner, same URL), each rule-5 path (a, b, c), the
greeting after a URL change, error text with and without a new success sentence, fragment-only and trailing-slash URL
changes, form null, sentence already on the form vs new, case differences, realistic Greenhouse / Lever / Ashby /
Workable / SmartRecruiters / Workday / SuccessFactors pages. Use realistic multi-sentence page text.
