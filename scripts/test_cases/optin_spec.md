# Which answer does an opt-in / consent checkbox on a job application get? (JSA-329)

Input: the label of a checkbox (or yes/no question) on a job application form. Output one of:
`"Yes"` (check it), `"No"` (leave it unchecked), `"ask"` (the rules do not know — the candidate decides).

The candidate's standing rules (2026-10-27):
- Recruitment **marketing** opt-ins → **No**, every time. This includes anything that asks to be sent campaigns,
  "recruiting campaign communications", marketing / promotional e-mails, newsletters, news, events, webinars, offers,
  products, surveys, or messages from partners / third parties. A box that mixes job news with any of these → No.
- **Talent community / job news** → **Yes**: joining the talent community / pool / network, being sent job alerts,
  updates about new / future / other / relevant job opportunities, openings or positions.
- **Required consent to the application itself** → **Yes**: privacy notice / policy, "I acknowledge", "I have read and
  agree", consent to process / store his personal data, being contacted (e-mail) about **his own application**, its
  status, the hiring / recruiting process or interviews.

An opt-in is a box that asks to *receive* / *get* / *be sent* / *be contacted with* something ("I agree to receive …",
"I would like to receive …", "Sign me up for …", "Send me …", "Subscribe to …"). The words "I agree" or "I consent" alone
do not make it a data consent: what is to be received decides. An opt-in to receive something that is neither job news
nor marketing as listed above ("I agree to receive communications from Acme", "I consent to receive information") →
`"ask"`.

Text-message / SMS consent questions are out of scope (another rule); do not write cases about SMS.
