# Does a Workday application have an education section?

Before submitting, a checker makes sure every school of the candidate appears on the Workday Review page — but only when
the application actually has an education section; some tenants have none (only work experience, languages, resume).
Inputs: answered_keys — the keys of answers the runner gave, formatted "<section>||<label>", e.g.
"Education 1||School or University", "Work Experience 2||Company", "My Information||Phone Number"; review_text — the
text of the Review page.
Return true when ANY answered key's section starts with "Education " followed by a number, OR the review text contains the
word "education" (as a word, any case) or the phrase "School or University". Otherwise false.
Words merely containing "education" inside another word (e.g. "coeducational") do not count; "Education" as a heading,
"Education 1", "Highest Education" do.
