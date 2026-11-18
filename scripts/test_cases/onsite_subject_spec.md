# Spec: who must be on site? (JSA-324)

An application-form question mentions being on site / in the office / in person / hybrid / commuting. Decide whether it
asks about THE APPLICANT being on site (then a fixed "on-site" answer may be used), or about SOMEONE ELSE.

about_applicant(question) -> true | false
- true when the question asks whether the applicant can / will / is willing / is able to work on site, in the office,
  hybrid or in person, commute, or come in N days a week — directly ("Are you able to work onsite 3 days a week?"),
  as a willingness phrase without "you" ("Willing to work on-site?"), or after a statement about the role ("This role is
  hybrid in NYC. Can you commit to that?"), including when other people are mentioned too ("Our engineers work on site in
  Austin; will you be able to join them on site?").
- false when the people on site are someone else and the applicant is not asked to be on site: e.g. "Are Dell
  personnel on site at your employer's facilities?", "Do our technicians work on site at your current company?",
  "Are any of the vendor's staff in the office at your workplace on a regular basis?". "your employer" / "your company" /
  "your facilities" alone does not make the applicant the subject.
