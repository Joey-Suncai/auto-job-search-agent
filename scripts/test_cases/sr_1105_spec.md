# SmartRecruiters fixes (2026-11-05): form URL company case + four form-question answers

## 1. form_url(store_url, api) -> string | null
A SmartRecruiters posting URL in the job store is `https://jobs.smartrecruiters.com/<company>/<numeric id>[-slug]` or
`https://jobs.smartrecruiters.com/oneclick-ui/company/<company>/publication/<uuid>`. The program looks the posting up in the
public posting API and gets back an object `api` (or the lookup fails: `api` is the string "ERROR").
The application form URL is
`https://jobs.smartrecruiters.com/oneclick-ui/company/<C>/publication/<uuid>?dcr_ci=<C>`, where:
- `<uuid>` = `api.uuid`;
- `<C>` = the company identifier **exactly as the API writes it** (the form is case-sensitive: `m3usa` opens an "expired"
  page, `an employer` the real form): `api.company.identifier`; if that is missing, the first path part of `api.applyUrl`, else of
  `api.postingUrl` (a path part `oneclick-ui` does not count); if none of these exist, the company as written in the store URL.
- The result is null when `api.uuid` is missing or `api.active` is false (the posting is closed).
- When the lookup fails ("ERROR"): for a oneclick-ui store URL the form URL is built from the store URL's own company and
  uuid (lower-cased uuid); for a numeric-id store URL the program raises an error — the case expects the string "RAISES".

## 2. answer(label, type, options) — four kinds of form questions
The candidate: an adult (over 18), an F-1 student who does NOT need visa sponsorship now (internship on CPT) but WILL need
sponsorship in the future (H-1B). He certifies his application is truthful. Expected outcomes:
- `{"value": "<text>"}` — the answer typed / the option picked;
- `{"leave": true}` — the box is deliberately left empty, and it is NOT reported as an unknown question;
- `{"not_rule": "auth_kind"}` — whatever happens, the question must not be answered by the "kind of work authorization /
  visa type" rule (whose answer would be "CPT").

a) **Date of birth for minors.** A free-text (or date) box that asks for the date of birth / birth date / DOB only of people
   under 16–21 or of "minors" ("For individuals under 18 … please provide your date of birth. Otherwise, you may skip this
   question.") → `{"leave": true}`. Never "No", never a date. When the same kind of question comes with Yes / No options
   (e.g. "Are you under 18? If so, provide your date of birth" as a radio) → `{"value": "No"}`. A plain Yes/No "Are you under
   18?" → `{"value": "No"}`; "Are you at least 18 years of age?" → `{"value": "Yes"}`.
b) **Certification.** "I certify that all information provided in this form and in my resume is truthful, complete, and
   accurate." — as a Yes/No radio → `{"value": "Yes"}`; the same certification in other wordings ("I certify that the
   information in this application is true and correct", "I certify that all answers given are accurate") → Yes.
   A question that only asks him to "certify whether you are a previous employee" is NOT a certification of truthfulness →
   `{"value": "No"}` (he never worked there).
c) **Working WITHOUT sponsorship.** A Yes/No question that asks whether he can / is eligible / is authorized to work
   *without* (required / visa / employer) sponsorship, now or in the future ("Are you eligible to work at an employer without
   required sponsorship now or in the future?", "Can you work in the U.S. without the need for visa sponsorship in the
   future?") → `{"value": "No"}`, because he will need sponsorship. One that asks only about NOW ("Can you currently work
   without sponsorship?", "…without sponsorship at this time?") → `{"value": "Yes"}`. A question that asks whether he
   REQUIRES sponsorship ("Will you now or in the future require sponsorship …?") → `{"value": "Yes"}` even when a note
   after the question mark mentions "without sponsorship".
d) **"If not, type N/A".** A text box whose instruction uses "type" as a verb ("Did someone from our company suggest you
   apply? If so, please provide their name – if not type N/A.", "If you were referred, enter the name; if not, type N/A")
   → `{"not_rule": "auth_kind"}`. A real question about the kind of authorization ("What type of work authorization do you
   have?") is not part of this check.
