# Collect a batch's questions on one sheet — helpers

1. `parse_unknown(line)`: a runner's unknown-question line "[section 2: | step 3: | page 1: ]<question> (options: A / B / C)"
   → (question, options). The leading "section N:", "step N:" or "page N:" (any case) is dropped; the trailing
   "(options: …)" is split on " / " into the options; no such suffix → options [].
2. `qnorm(question)`: the merge key — lower case, leading numbering ("1.", "2.3 ", "a)", "Q4.") dropped, punctuation
   replaced by spaces, whitespace collapsed. Two questions with the same key are the same question.
3. `merge(items)`: items {folder, question, options, type} → one entry per question key, in this order: the entries asked by
   MORE folders first, then alphabetical (case-insensitive). Each entry lists its folders once each (first-seen order) and
   the union of the options (first-seen order). A question that is a human check (mentions CAPTCHA, "verify you are
   human", "not a robot", "count the number of") is not an entry: it goes to the human-check list. An entry with no
   options whose question starts with Why / How does / How do / Tell us / Describe / Explain (or mentions "cover letter"
   or "in your own words"), or whose type is textarea, is kind "essay"; every other entry is kind "fact". Empty questions
   are dropped.
4. `qa_args(entry, source)`: an entry with answer {"yes": true} → [--q, <question>, --source, <source>, --yes];
   {"no": true} → … --no; {"pick": "X"} → … --pick X; {"text": "T"} → … --text T; then, when the entry has options,
   --options "A|B|C". No answer (null / {}) → None.
