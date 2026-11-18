# Weekly spot check of the form prefetch's suggested answers (JSA-240)

Each morning the prefetch sheet lists questions the rules cannot answer. For most of them DeepSeek writes a SUGGESTED
answer {answer, fact, why} (answer = "ASK" when it cannot decide). The candidate later gives his own answer, which the
system saves in a question-and-answer table. Once a week the two are compared so that every disagreement becomes a rule.

## verdict(suggestion, joey, options) — one question
Inputs: suggestion = the suggested answer text (maybe "ASK"); joey = the candidate's saved answer text or null (no answer
saved yet); options = the option texts the form showed ([] for a text box).
- joey is null → "open" (not answered yet; not counted either way).
- suggestion is "ASK" (any case, spaces around ignored) and joey is given → "asked" (the suggestion declined; not counted
  as agree or disagree).
- both given: they AGREE when they are the same after normalising (lower case, punctuation and runs of spaces ignored, so
  "United States" = "united states." and "Yes" = "yes"), or, when options are given, when both pick the same option, where
  an answer picks the first option whose normalised text equals the normalised answer, else the first option whose
  normalised text starts with the normalised answer (the answer "No" picks "No, I do not" when no option is exactly "No").
  Otherwise "disagree".
- An empty / whitespace suggestion counts as "ASK"; an empty joey as null.

## report rows
audit(rows) takes a list of {question, suggestion, joey, options, fact, sheet} and returns counts {agree, disagree, asked, open}
and agreement = agree / (agree + disagree) rounded to 3 decimals (null when agree + disagree is 0), plus the list of the
disagreeing rows (question, suggestion, joey, fact) in input order. A question text that appears more than once in the
input (same question after lower-casing and collapsing spaces) is counted once: the LAST row wins.
