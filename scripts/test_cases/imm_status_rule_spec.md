# Spec: which answer rule takes an immigration-status / work-authorization fill-in (JSA-287)

Joey is an F-1 student. His immigration (visa) status is "F-1". His work authorization for internships is "CPT".
Two rules answer free-text / dropdown questions about this:
- immigration_status → "F-1": any question that asks for his immigration status or visa type / status / classification
  — e.g. "What is your current immigration status?", "If no, please provide your immigration status in the U.S.",
  "Please state your immigration status", "Immigration status", "Provide your visa classification".
- auth_kind → "CPT": a question that asks what kind / type / category of WORK AUTHORIZATION he has, or "if yes, what
  type" after a work-authorization question — e.g. "What type of work authorization do you have?", "If yes, what kind
  of authorization?". A question that says "immigration status" is never auth_kind.
Neither rule takes:
- a yes/no question that starts with "Are / Do / Does / Will / Would / Is / Have / Has / Can / Could you …"
  (e.g. "Do you have an immigration status that allows you to work?");
- a question about sponsorship ("… require sponsorship to maintain your immigration status?") — other rules handle it;
- a question about petitions, a number of months / years, or "how long".
