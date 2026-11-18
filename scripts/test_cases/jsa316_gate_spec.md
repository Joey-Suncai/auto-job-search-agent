# Critical-question class and fact gate for questions about supporting military / defense missions (JSA-316)

Two pure functions check answers on job-application forms for one candidate before submit and in an audit.

field_class(label) → class: "critical" or "non-critical", and a group. Questions about supporting / contributing to
military or defense missions (willing / able / comfortable to work on defense or military projects, any reason he would
not be able to support the U.S. military or armed forces, objections to defense work) are "critical" with group
"defense" — even when the label also mentions travel, on-site work or relocation. Veteran / military-service
self-identification questions ("Are you a protected veteran?", "hiring and supporting military service members and their
spouses — disclose your status") are critical with group "eeo", not "defense". A question about his own past government
or military employment is not "defense" (it may be any other group).

gate(label, value) → "pass" or "block:defense" (other blocks are out of scope; such labels expect "pass" here).
The candidate has one saved answer: for "Are there any reasons why you would not be able to fully contribute in support
of the U.S. military and allied forces?" and questions of the same kind (any reason he would / could not (fully)
contribute / support / work … military, defense, armed forces, allied forces) the saved answer is Yes.
- A defense-support question with the saved answer: value Yes passes; No / Other / anything else blocks (block:defense).
- A defense-support question with no saved answer (e.g. "Are you willing to work on Department of Defense projects?"):
  any value blocks (block:defense) — the candidate must answer.
- Questions about his own government / military employment ("Are you a current or former government employee?"),
  veteran status, and other questions with no defense-support wording: pass, whatever the value.
