# role_library.specific(phrase) — is a discovered JD phrase specific enough to list as a resume keyword?
Split the phrase on whitespace.
- Two or more words → True ("Product Management", "AI tools", "data science").
- One word that is entirely upper-case (Python's str.isupper: all cased characters are upper-case, digits allowed) → True only if it has 3 or more characters ("CRM", "SQL" → True; "AI", "ML", "S3" → False).
- Any other single word → True when a character after the first is upper-case, or the word contains a digit ("SaaS", "PyTorch", "iOS", "k8s" → True); otherwise False ("product", "Engineering", "data", "Python" → False).
