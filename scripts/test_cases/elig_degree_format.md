Return a JSON array of 26 cases:
{"name": "snake_case_unique", "candidate": {"degree_level": "bachelors" | "masters" | "phd"},
 "title": "Data Analyst Intern, Summer 2027", "loc": "Chicago, IL", "level": "Internship",
 "text": "a realistic job description of AT LEAST 300 characters: responsibilities, qualifications, and the degree sentence under test; it states that the company sponsors visas",
 "expect": "Eligible" | "Review" | "Ineligible"}
Keep every other detail neutral: U.S. city, Summer 2027 internship (May–August), no graduation window, no duration limit,
no part-time, no MBA, no citizenship or clearance wording. Include pairs where the same job flips between candidates, and a
couple of full-time (level "New grad", title without "intern") cases that must not change.
