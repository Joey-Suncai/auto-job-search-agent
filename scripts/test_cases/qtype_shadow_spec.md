# Shadow comparison: the question-type layer's answer vs the live answer (JSA-361)

The layer's answer is one of: none (the layer asks), ("yes", true|false), ("text", "<lower-case text>"), ("pick",
["/regex/i", ...]) or ("key", "<fact key>") (no stored value — the rule computes it). The live answer is the text the
runner planned (may be empty).

Kinds:
- layer asks: live non-empty → **layer_asks**; live empty → **both_ask**;
- layer answers but live is empty → **live_asks**;
- ("yes", b): read the live text as yes when it starts with yes / y / true / checked / "I am", "I do", "I will", "I have",
  "I agree", "I consent", "I accept", "I acknowledge", "I understand"; as no when it starts with no / n / false /
  unchecked / not / "I am not", "I do not", "I don't", "I will not", "I won't", "I have not", "I haven't", "I decline" (the
  no forms win when both fit). Same as b → **agree**, opposite → **differ**, neither → **cannot_compare**;
- ("text", t): the live text in lower case, trimmed, without a final period, equals t (also without a final period) →
  **agree**, else **differ**;
- ("pick", patterns): any pattern (a JavaScript-style /…/flags regex) matches the live text → **agree**, else **differ**;
- ("key", k) → **cannot_compare**.
Examples: live "No, I do not require sponsorship" vs ("yes", false) → agree; live "Yes" vs ("yes", false) → differ;
live "Chicago, IL" vs ("text", "chicago, il") → agree; live "Master's Degree" vs ("pick", ["/master/i"]) → agree.

The layer's answer for the shadow comes from its reading with one difference from the Haiku comparison: a choice /
multi-choice reading whose fact has option patterns gives ("pick", patterns) even when the fact also has a text, so a live
option like "Asian (Not Hispanic or Latino)" is matched by pattern.
