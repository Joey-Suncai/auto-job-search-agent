# Identity restrictions in the application form (JSA-231, Joey 2026-11-06)

Some postings say nothing about citizenship in the job description, but the application form asks a question that
states one. Each form question has a label (and maybe a description and answer options). The check reads ONE question
and returns a kind (or none), and whether it blocks the candidate.

Kinds:
- export_control: the question mentions export controls (export control / export-controlled / ITAR / EAR / deemed export /
  International Traffic in Arms) AND an identity status (U.S. citizen / national / person, citizenship, permanent
  resident, green card, protected individual, refugee, asylee, 8 USC 1324b) — in the label, description or the options.
  Example: "This position requires access to information and technology that is subject to US export controls. Are you
  any of the following 'protected individuals' …?" with options "US citizen or national", "US permanent resident", …
- export_control_maybe: an export_control question that leaves room for a licence: "may require", "or otherwise eligible
  for deemed export licensing", "committed to compliance with export control laws", "to assess our export compliance".
- citizenship: the question states the position requires / is only for / is limited to U.S. citizens (or U.S. persons):
  "This position requires U.S. citizenship pursuant to a government contract. Are you a U.S. citizen?", "Only US
  Citizens will be considered for this position.", "U.S. citizens only".
- clearance: the question states a security clearance is required ("This role requires an active Secret clearance",
  "Active TS/SCI clearance required", "must be able to obtain a DoD security clearance").
- none: anything else, in particular questions that only ASK about status without stating a requirement: "Are you a U.S.
  citizen?", "Are you legally authorized to work in the United States?", "Will you now or in the future require visa
  sponsorship?", "What is your citizenship?", EEO / veteran questions, "Do you have experience with export compliance
  software?" (export words but no identity status).
Blocks: export_control, citizenship and clearance block a candidate who is not a U.S. citizen or permanent resident.
export_control_maybe never blocks (a person reads it). A citizen / permanent resident is never blocked by this check.

## Sanctions screens are not restrictions (JSA-237, 2026-11-06)
A question about U.S. sanctions / embargoed countries — it mentions sanctions, or names Cuba, Iran, North Korea, Syria,
Crimea, Donetsk or Luhansk — and does NOT name a U.S. identity status (U.S. citizen / person / national, United States
citizen / person / national, protected individual, green card, 8 USC) is a sanctions screen, not a restriction: find()
returns nothing for it, even when it also says "export controls" (e.g. a Greenhouse employer: "Please confirm whether any of the
below applies … compliance with U.S. sanctions and export controls", options "Citizen or permanent resident of Cuba,
Iran, North Korea, or Syria / … / None of the above"). If such a question also names a U.S. identity status, the normal
rules above apply.

## Asking is not requiring (JSA-237 full prefetch, 2026-11-06)
A block (export_control / citizenship / clearance) needs the form to STATE that the position requires the status or involves
the controlled access: "requires", "must be", "limited to", "involves access to / work with", "will have access", "subject
to" export-controlled technology. These are questions for the person instead (kind export_control_maybe /
citizenship_maybe / clearance_maybe, never block):
- a license question: "Would you require an export license …", "for the (sole) purpose of determining export licensing …,
  please list any countries of which you are a citizen", "would you meet the requirements for a deemed export license";
- a conditional or partial statement: "If this role requires a security clearance, do you …", "Some of the work …
  requires …", "certain positions / roles / contracts require …", "may be required", "in which you required a clearance";
- export / identity words with no requirement statement at all (e.g. "Are you a US Person under ITAR? Please select").
"Do you meet this requirement?" after a stated requirement ("This position is limited to U.S. persons.") is still a block.
