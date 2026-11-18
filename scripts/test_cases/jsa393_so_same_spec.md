# second_opinion.same — the rule's answer and the model's answer for one form question (JSA-393)

same(rule_value, model_value, options) says whether two answers are the same answer. A wrong "same" lets a wrong rule answer
through the safety net, so it must be strict about NAMES, schools, degrees and majors.

## Normalising
Compare lower-case with every character other than a-z and 0-9 removed, after dropping ONE trailing bracketed note
("F-1 (CPT)" = "F-1"). An empty side, or a model answer of null, is never the same.

## Equal
Equal after normalising → same.

## One answer is a longer version of the other (no options)
When the normalised shorter answer is a PREFIX of the normalised longer one, they are the same ONLY when the longer one
continues the shorter one with a separator, i.e. in the original text what follows the shorter answer's words starts with a
comma, semicolon, colon, dash (-, –, —) or an opening bracket: "Yes" = "Yes, I am authorized", "No" = "No - I would need
sponsorship", "F-1" = "F-1: student visa". Or when the shorter answer is exactly "yes", "no" or "n/a" (any case), whatever follows.
A longer version that just adds more words is a DIFFERENT answer: "Hyde Park" ≠ "Hyde Park Investment Services",
"Computer Science" ≠ "Computer Science and Economics", "Master of Science" ≠ "Master of Science in Data Science",
"University of Chicago" ≠ "University of Chicago Booth School of Business", "a Greenhouse employer" ≠ "a Greenhouse employer Capital".

## With options
Unchanged: both answers must name the same option, where an answer names the first option equal to it, or one that is a
prefix of it or that it is a prefix of (normalised); same only when both name the same non-empty set of options.

A trailing generic word does not make a different answer: what follows is only "degree", "program" or "level" (any case): "Master's" = "Master's Degree" (added after the 2026-11-17 replay: a false stop on the Degree box).

## Review changes (2026-11-17, same day)
- A continuation that contains a qualifier word (not, no, never, but, however, unless, require(d), need(s), sponsor…, except, only, n't)
  is NEVER the same answer ("No" ≠ "No - I would need sponsorship", "Yes" ≠ "Yes, I am not authorized").
- yes / no / n/a match a longer answer only at a whole word ("No" ≠ "Not sure", "Yes" ≠ "Yesterday").
- Generic trailing words that add nothing: s / es (plural), degree, program, level, "of America", "student visa", "visa".
- A dash separates only when followed by a space and a lowercase word ("University of Chicago - Booth" is a different entity).
