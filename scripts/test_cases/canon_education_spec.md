# Which education fact a form label asks for (canonical audit)

Before a submit the runner checks the page's answers for high-stakes fields against the candidate's facts. For
education labels, decide which check applies:
- "education_field": the label asks for the FIELD of study — "Major", "Field of Study", "What is your major?",
  "Intended field of study". NOT when the label asks which school the candidate attends, even if it mentions a major
  ("What school are you currently attending for your major?" is not a field-of-study question).
- "degree_level": the label asks for the degree LEVEL — "Degree", "Degree level", "Highest level of education",
  "Education 1 || Degree", "Diploma". NOT a free-text request for a degree program together with a school name
  ("Please include your completed degree program and school name for verification purposes").
- "school": the label names a school / university / institution as the thing asked, as a plain field label
  ("School", "University", "Institution name"). A label that is a question (contains "?"), or is about dates, graduation,
  GPA, enrollment or employment, is not the school check.
- otherwise null.
For "Please include your completed degree program and school name for verification purposes" the answer is "school".
For "What school are you currently attending for your major?" the answer is null (it is a question).
