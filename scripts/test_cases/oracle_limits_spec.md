# Spec: an Oracle application dry run that respects the page's own limits (JSA-312)

The robot fills one section of an Oracle Recruiting Cloud application form. For each text box (input or textarea) it
knows:
- `label`, `required` (bool), `kind` ("text" | "textarea").
- `limits`: what the page told it before filling — {"max": int|null, "min": int|null, "format": "url"|null} — from the
  box's attributes, its hint text, or the platform's question data. May be null (nothing known).
- `source`: where the planned answer comes from: "rule" (a saved fact answer) or "draft" (a prose answer written earlier
  into open_answers.md for an essay question; essay questions are textareas whose label is longer than 100 characters
  or starts with Describe / Tell us / Share / Explain).
- `answer`: the planned text (may be {"repeat": chunk, "times": n} for long text = chunk*n).
- after filling, the page may mark the row: `page_invalid` (bool) and `page_error` (the row's text including the error
  sentence, e.g. "What is your current GPA? * 2 out of 50 characters The value must have at least 3 characters.").

Before judging, a url box (limits.format "url", or a label that is only a link name — see below) whose rule answer is a
bare web address without a scheme ("linkedin.com/in/x", "www.example.org", "github.com/user") gets "https://" put in
front (the same address); then it is judged as that full address. Text that is not an address ("N/A", "see resume",
"my linkedin") is not changed.

Expected outcome per row (`expect`):
- "stop_ask": a rule answer that breaks the limits (longer than max, shorter than min — counted after trimming —, or a
  url box whose answer does not start with http:// or https://) in a REQUIRED box: never typed; the row stops the run and
  the candidate is asked.
- "leave": the same in an OPTIONAL box: left empty, the run goes on.
- "redraft": a draft answer that breaks the limits: not typed; the question goes back to the drafting step with the
  page's real maximum (`expect_limit` = limits.max, or 1500 when no maximum is known) and `expect_min` (= limits.min or
  null). A draft that fits is "fill".
- "fill": the answer fits; it is typed.
- "page_stop": the answer fit what was known before filling, but after the fill the page itself marks the row invalid
  (`page_invalid` true) → the row fails and the run stops. Any error the page reports counts, whatever it says.
- When nothing is known (`limits` null) and the page marks nothing, a rule answer is "fill"; except that a box whose
  label is only a link name ("Link 1", "Link 2", "Website", "Portfolio", "LinkedIn Profile", "GitHub") always wants an
  http(s):// address.

Replay of the real incident (Oracle, an employer, 2026-11-11), all must be in the cases:
- required "What is your current degree minor? if applicable." (textarea, limits max 50 min 5, rule answer "None") → stop_ask;
  with "Not applicable" → fill.
- required career-aspirations question, label "Would you please share some details about your future career aspirations?
  Anything you'd like the hiring review team to know when reviewing your candidacy?" (textarea, platform max 200, a 1086-character
  draft) → redraft with limit 200; a 194-character draft → fill.
- required "Link 1" (text, no limits known, rule answer "linkedin.com/in/alexdoe") → fill (typed as
  "https://linkedin.com/in/alexdoe"); "https://www.linkedin.com/in/alexdoe" → fill; "N/A" → stop_ask.
- the same "None" when the page had told nothing before filling (limits null) but marks it invalid after the fill with
  "4 out of 50 characters The value must have at least 5 characters." → page_stop.
