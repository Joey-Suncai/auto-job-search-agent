Return {"cases": [...]}. Each case: {"name": str, "fn": "form_url" | "answer", "args": {...}, "expect": ..., "spec_quote": str, "ambiguous": false}.
form_url: args {"store_url": str, "api": object | "ERROR"}, expect a URL string, null, or "RAISES".
answer: args {"label": str, "type": "text" | "textarea" | "date" | "radio" | "select", "options": [str]}, expect {"value": str} | {"leave": true} | {"not_rule": "auth_kind"}.
Write 28 cases: form_url 10 (identifier case kept, fallback to applyUrl, to postingUrl, to the store URL, inactive, no uuid, ERROR on both URL kinds), answer 18 (DOB for minors 5 incl. one radio and one plain age question, certify 4 incl. the "previous employee" near miss, without-sponsorship 6 incl. two require-sponsorship questions, "type N/A" 3).
