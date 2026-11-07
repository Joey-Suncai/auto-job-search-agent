# Spec: drop_private_lines(text, path) — private evidence lines in the public export (JSA-085)
Skills keep, under each problem type, a line that starts with "Seen:" listing the companies / dates that showed the problem.
That line is private. For a path ending in ".md": every line whose first non-space characters are "Seen:" is removed (the
whole line, including its line break); all other lines stay exactly as they are, in order. "Seen:" in the middle of a line
does not count; "seen:" (lower case) and "Seen -" do not count. Any other file type (.py, .json, .js, .txt) is returned
unchanged, even if it has "Seen:" lines.
