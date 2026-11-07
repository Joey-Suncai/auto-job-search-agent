# wrong_program(text) -> bool
The candidate's degree program is "M.S. Applied Data Science" (University of Chicago). Return True when the text names
that degree program as plain "Data Science": a phrase where "master's" / "masters" / "M.S." / "MS" / "degree" / "program" /
"graduate studies" is followed, within about 30 characters and inside the same sentence, by "in Data Science" that is NOT
"in Applied Data Science". Examples that are True: "completing a Master's in Data Science", "my master's is in Data Science",
"an M.S. in Data Science at UChicago", "my degree is in Data Science and Economics". False: "M.S. in Applied Data Science",
"a career in data science" (no degree word), "Data Science intern", "experience in data science projects", empty text.
Case-insensitive.
