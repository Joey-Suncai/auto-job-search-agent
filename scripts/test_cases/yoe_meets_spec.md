# "Do you meet the years of experience required?" (JSA-105, 2026-11-03)
An answer-rule engine maps an application-form question (label, field type, options) plus the text of the job description (JD) to one answer; for a select or radio the answer must be one of the options, copied exactly.

The candidate is a graduate student applying to internships and new-grad roles. Some forms ask whether he MEETS the years of experience the position requires. This is a yes/no question about the JD's own requirement — it is NOT the question "how many years of experience do you have".

Rule:
- The question asks whether the applicant meets / has / satisfies the years (or minimum years) of experience required for / listed for this position or role (e.g. "Do you meet the years of experience required for this position?", "Do you have the minimum years of experience required for this role?", "Do you possess the required years of experience listed in the job description?").
- If the JD states no required number of years of work / professional / industry / relevant experience (typical internship and new-grad postings; also when it says "no prior experience required", "0 years", "0+ years", "0-2 years" (the minimum is 0), or only mentions years of college, years of age, degree length, "class of 2027", graduation within a year, or how many years the company has existed), the answer is "Yes" (the option starting with Yes).
- If the JD states any minimum number of years of experience above zero (required OR preferred, in digits or words: "1+ years of experience", "at least two years of professional experience", "3-5 years of relevant industry experience", "one year of related work experience", "2 yrs experience with SQL"), the engine must NOT answer: it hands the question to the candidate. Expected result "ASK".
- If no JD text is available (empty), the expected result is "ASK".
- Other questions about experience are different questions and must not be answered by this rule: "How many years of professional experience do you have?", "Years of experience with Python", "Do you have experience with Tableau?". For these expect "NOT_THIS_RULE".
