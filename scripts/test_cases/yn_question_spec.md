# Spec: does a form question ask only yes / no, or does it ask for a value? (JSA-325)

yes_no_only(question) -> true | false

A form question (one or more sentences, may contain parentheses) is "yes/no only" when:
- at least one of its sentences that ends with "?" starts with a yes/no word: are, is, am, do, does, did, will, would,
  can, could, have, has, had, were, was, should, may, must (leading punctuation or "(" ignored); AND
- none of its sentences asks for a value: a sentence (or one starting with "If yes," / "If so," / "If applicable,", or
  inside "(" ) that starts with what, which, who, whom, whose, where, when, how, why, name, list, enter, provide,
  specify, state, indicate, or "please list / provide / enter / specify / state / name / indicate / write / type /
  share / tell".
Otherwise false. A bare label with no "?" ("Current Employer", "Major", "Email") is false.
Examples: "Is your current employer a reseller of Dell?" → true. "Are you currently employed? If so, what is your
current employer?" → false. "Do you have a preferred name? If so, please enter it." → false. "(if yes, please note
Dell may contact your employer)" does not ask for a value ("please note" is not in the list).
