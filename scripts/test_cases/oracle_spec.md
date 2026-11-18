# run_oracle.py pure helpers — spec (JSA-048, Oracle Recruiting Cloud)

All string comparisons are as described per function. `N(s)` = whitespace collapsed to single spaces and trimmed.

## parse_posting(url)
Oracle Candidate Experience URL → {'host', 'lang', 'site', 'job'} or None. Accepts the job page (`/hcmUI/CandidateExperience/en/sites/CX_1/job/8491`), its apply pages (`…/job/8491/apply/email`, `/apply/section/2`), the older `…/sites/CX_1/requisitions/preview/8491` form, any query / fragment; host must be an `*.oraclecloud.com` name with `.fa.` in it (the Fusion Applications pod), scheme http(s).

## apply_url(url)
Posting URL → the apply flow's e-mail page `https://<host>/hcmUI/CandidateExperience/<lang>/sites/<site>/job/<id>/apply/email` (None when it is not an Oracle posting).

## classify(url, text)
Where the tab is: 'closed' (posting no longer open) · 'applied' (this e-mail already applied to the job) · 'done' (a thank-you / submitted page) · 'code' (the one-time verification code page) · 'email' (the e-mail step) · 'form' (a section of the apply flow) · 'job' (the job description page) · 'limited' (too many attempts — try again later) · 'unknown'.

## is_final(button)
True when the apply flow's forward button would hand in the application: 'Submit', 'Submit Application', 'Finish', 'Apply', 'Send' (any case); False for 'Next', 'Continue', 'Save and Continue', 'Back', 'Cancel' and an empty text.

## clean_label(label)
On-page label → the label the answer rules read: whitespace collapsed, a trailing required star / '(required)' / 'Required' dropped, a leading star dropped. 'Country *' → 'Country'.

## pick_option(want, options)
The option to click for answer `want`: an exact match (case / space-insensitive) first, then the single option that starts with `want`, then the single option that contains `want` as whole words; None when there is none or the starts-with / contains steps find more than one.

## geo_same(want, got)
Address read-back: equal ignoring case / spaces; a U.S. state name equals its two-letter code ('Illinois' = 'IL'); a city option shown as 'Chicago, Cook, IL' equals 'Chicago' (its first comma part).

## geo_pick(want, options, state=None)
Option to click in an Oracle geography list (City / County / Postal Code, options like 'Chicago, Cook, IL' or '60601'): an exact option first; else the options whose first comma part equals `want` — one left → it; several → the one that also names `state` (name or two-letter code) as a later comma part; None when still not exactly one.

## email_consent(text, terms_text=None)
The legal-disclaimer box some tenants put on the e-mail step → 'tick' or 'ask'. 'ask' (Joey approves the wording once, `--consent-ok`) when the box text binds the candidate to arbitration / a waiver ("be bound by"), consents to automated calls / texts, marketing or recruiting messages; when it names "terms and conditions" / "terms of use" and the linked terms text (`terms_text`, read from the tenant's dialog) is missing or itself contains such wording or no privacy wording; and for an empty or unrelated text (never ticked blind). 'tick' when what remains is only the privacy / data-processing notice for this application.

## is_other_followup(label)
True for the free-text box Oracle shows after an 'Other' pick: 'If other, please specify', 'Other (please specify)', 'If you selected Other, please explain', 'Please specify'; False for ordinary questions that merely contain 'other' ('Do you have any other names?', 'Other languages spoken').

## same(want, got)
Read-back comparison: case / space-insensitive; phones by the last 10 digits; lists (multi-select) as sets.
