# SmartRecruiters required employment declarations (JSA-326, Arista 11-11)

Joey agreed (JSA-326, BACKLOG acceptance) that Arista's three required declaration checkboxes are all ticked. They are
acknowledgements of the hiring process, not statements about Joey's history. `declaration_rule(label)` takes the
checkbox's text (it may start with "* ") and returns the rule name, or None when the text is not one of the three kinds:
- "background_release": the person grants permission to any person, firm or corporation to release information regarding
  past work / employment to the Company (and waives claims). Example: "I hereby grant permission to any person, firm or
  corporation to release to the Company or its representatives any and all information regarding my past work or
  employment … I waive any and all claims …"
- "at_will": the person understands that employment, if hired, is on an at-will basis and nothing in the application or an
  interview creates an employment contract. Example: "I understand that nothing contained in the application … is intended
  to create an employment contract … my employment would be on an at-will basis …"
- "i9_verify": the person understands that all persons hired must verify identity and eligibility to work in the United
  States and complete the employment eligibility verification document upon hire. Example: "I understand that all persons
  hired will be required to verify identity and eligibility to work in the United States and to complete the required
  employment eligibility verification document upon hire."
Everything else returns None — in particular: marketing / newsletter / SMS consent, "I certify that I have not knowingly
withheld any information" (a separate rule), any question about criminal convictions, relocation, background-check
*results*, work authorization status, a negated sentence ("I do not grant permission …", "I do not understand …"), and
short texts that merely mention "at-will" without the understanding of an employment contract (e.g. "Are you currently
an at-will employee?").
