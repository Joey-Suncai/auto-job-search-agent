# Spec: SuccessFactors education dates and a covered Apply button (2026-11-05 fourth round)

1. **Education date wanted** — `edu_date_want(label, edu, required, fmt)` returns the text to type into one date box of an
   education row, or null.
   - `label` is the box's label; a leading "*", a trailing ":" and surrounding spaces are ignored, case does not matter.
     "From Date", "Start Date", "From", "Begin Date" are START boxes; "To Date", "End Date", "To" are END boxes; any other
     label (e.g. "Graduation Year", "Today's Date") → null.
   - `edu` is the education entry: {"school", "start": "YYYY-MM" or missing, "end": "YYYY-MM" or missing}.
   - START box → the FIRST day of the start month; null when the entry has no start (or it cannot be read) — the caller
     then asks the person, it never guesses.
   - END box → only when `required` is true: the LAST day of the end month (e.g. 2026-02 → the 28th; 2028-02 → the 29th);
     not required → null (left empty); required but no end → null.
   - `fmt` is the box's own date pattern, built from the tokens `yyyy` (4-digit year), `MM` (2-digit month), `dd` (2-digit
     day), `M` / `d` (no leading zero) and literal separators. Missing / empty fmt = "MM/dd/yyyy".
     Example: start "2026-09" with "MM/dd/yyyy" → "09/01/2026"; with "dd/MM/yyyy" → "01/09/2026"; with "yyyy-MM-dd" →
     "2026-09-01"; with "M/d/yyyy" → "9/1/2026".
2. **What covers the Apply button** — `cover_action(el)`. `el` describes the top-most element at the centre of the Apply
   button (or its nearest fixed / sticky ancestor), or is null when nothing was found:
   {"self": bool (it is the button or inside it), "tag", "id", "cls", "role", "title", "name", "src", "text" (first ~200
   characters), "fixed": bool (position fixed or sticky)}. Returns one of:
   - "none" — el is null or `self` is true (nothing covers the button);
   - "stop" — a CAPTCHA (any of id / cls / title / name / src mentions recaptcha, hcaptcha or captcha), or anything not
     listed below (a dialog, a session-timeout message, an ordinary page element, a non-fixed element);
   - "hide_chat" — a chat widget: id / cls / title / name / src name a chat bot / chatbot, live chat, a chat widget, or a chat
     vendor (Intercom, Drift, Zendesk, Ada), and nothing in them mentions cookies or consent;
   - "hide_banner" — a fixed / sticky cookie or consent banner: its id, cls, role, title or text mentions cookie(s),
     consent, OneTrust, TrustArc, GDPR or "cookiemanager". A cookie banner that is NOT fixed / sticky → "stop".
   The banner is only hidden from view for the one click; its Accept / Reject / Close buttons are never pressed.
3. **Outcome of pressing Apply** — `press_result(clicked, confirmed_by, button_left)` → [status, note].
   - `confirmed_by` set ("page" or "email") → ["submitted", null] whatever the other two are.
   - clicked true, not confirmed → ["unconfirmed", note] with the note starting "pressed the final button".
   - clicked false and the Apply button is still on the page (`button_left` false) → ["blocked", note]: the note starts
     "Apply not pressed" and says nothing was submitted; it never says "pressed the final button".
   - clicked false, the button has left the page (`button_left` true), not confirmed → ["unconfirmed", note]: the note
     starts "the Apply click failed" and never contains "pressed the final button".
Return {"cases": [...]}. Each case: {"name": str, "fn": "edu_date_want" | "cover_action" | "press_result", "args": {...},
"expect": ..., "spec_quote": str, "ambiguous": false}.
