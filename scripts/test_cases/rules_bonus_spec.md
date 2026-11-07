# Bonus expectation dropdown

Rule (candidate's preference): a question asking for his bonus expectations / expected bonus / bonus target / bonus range,
with options given as percentage bands, is answered with the LOWEST band (the band whose first percentage is smallest),
whatever the order of the options. Options without a percentage ("Prefer not to say", "Not applicable") are never chosen
when a percentage band exists. A question that is not about a bonus (e.g. "Desired salary", "Sign-on bonus eligible employees
must…" statements are still bonus questions only if they ask for his expectation) is not this rule.
Output: the chosen option text, or "none" when the rule does not apply.
