# Sponsorship statement in a job description

A job-eligibility checker reads the full text of a job description for an F-1 international student who needs visa
sponsorship. It must report NO_SPONSORSHIP whenever the employer says it will not sponsor a work visa, including when the
JD states it as a labelled field in a details block, e.g. "Sponsorship: Not Available", "Visa Sponsorship: No",
"Sponsorship - None", "Immigration Sponsorship: Not offered".

It must NOT report NO_SPONSORSHIP when:
- the employer offers sponsorship ("Visa Sponsorship: Yes", "Sponsorship: Available", "we will sponsor H-1B visas");
- "sponsor" means something else: a "company-sponsored medical plan", "event sponsorship opportunities", "sponsorship,
  ticketing and hospitality sales", "executive sponsor";
- the text says the applicant can "opt out" / "opt in" of something (AI screening, text messages) — "opt" here is not OPT;
- the text only mentions U.S. Citizenship and Immigration Services / E-Verify, or an EEO statement about citizenship status.

Plain-sentence refusals ("We are unable to sponsor", "F-1 / OPT / CPT students are not eligible", "no visa sponsorship", "without sponsorship now or in the future",
"sponsorship is not available") are NO_SPONSORSHIP as well.

Each case is a short JD text; the answer is whether NO_SPONSORSHIP is reported (true / false).

Also NO_SPONSORSHIP (2026-11-01, ConocoPhillips): "Must be legally authorized to work in the United States on a full-time basis for anyone other than current employer and/or education institution" — authorization for anyone other than the school / current employer excludes F-1 CPT.
