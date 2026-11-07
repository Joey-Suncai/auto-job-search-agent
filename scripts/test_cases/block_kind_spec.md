# Kind of a Workday repeat block from its heading

Workday application pages show repeatable blocks with headings such as "Work Experience 1", "Education 2",
"Languages 1". Tenants use their own names. Classify a heading:
- "languages" — the heading mentions language(s) ("Languages 1", "Language Skills 2").
- "education" — it mentions education or academic ("Education 1", "Academic Experience 2", "Academic History 1",
  "Educational Background 3"), even when it also contains the word "Experience".
- "work" — otherwise, when it mentions work, experience or employment ("Work Experience 1", "Professional Experience 2",
  "Employment History 3", "Work History 1").
- null — none of these ("Websites 1", "Certifications 2", "References 1").
