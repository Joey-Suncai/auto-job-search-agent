Return {"cases": [...]}. Each case is one call of one helper:
{"name": str (unique), "fn": "chat_overlay" | "label_from_options" | "split_fix" | "canon_label",
 "args": {...}, "expect": ..., "spec_quote": str, "ambiguous": false}

- chat_overlay: args {"el": {"tag": str, "id": str, "cls": str, "title": str, "name": str, "src": str}}; expect true / false.
- label_from_options: args {"label": str, "options": [str, ...]}; expect a string.
- split_fix: args {"field": {"type": str, "label": str, "value": str}}; expect true / false.
- canon_label: args {"label": str, "kind": "work" | "edu"}; expect a string.

Write about 7 chat_overlay, 7 label_from_options, 7 split_fix and 7 canon_label cases: realistic SuccessFactors / Phenom
career-site markup (e.g. iframe id "phenomChatbotIframe", OneTrust banners, reCAPTCHA iframes, YouTube embeds), near misses,
labels with "*" and ":", wrong kinds.
