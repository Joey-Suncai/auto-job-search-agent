# Does a bare "Yes" or "No" answer this free-text box on a job application? (JSA-322)

Input: the label (question) of a text box on an application form. Output true when the box asks a yes/no question that
a single word "Yes" or "No" fully answers; false otherwise.

True: the asking sentence (the text before the first '?') starts with a yes/no question word — are, is, am, do, does,
did, will, would, can, could, have, has, had, were, was, should, may, must — and does not ask for more text; OR the label
says to answer yes or no ("(Yes/No)", "(Y/N)", "yes or no", "answer Yes"). Text after the first '?' ("Do you need
sponsorship? If so, please list …") does not change the answer.

False: the label is not a question (a field name like "Family member names", "Visa type", "Comments"); it starts with a
wh-word (what, which, why, how, when, where, who) or an instruction (please describe, list, provide, explain); or the
asking sentence invites more text: "any other / anything else / any additional / any further …", "additional
information / context / details / comments", "context", "elaborate", "explain", "describe", "details", "comments",
"share", "tell us", "let us know more / about", "list", "name(s)".
