# message_text(text) -> str
SmartRecruiters' "Message to the Hiring Team" box refuses the character ';'. Every ';' is replaced by ',' with exactly one
space after it and no space before it (spaces around the ';' collapse). If the ';' is followed by a line break, the comma
is followed directly by that line break (no trailing space). No other character changes; text without ';' is returned
unchanged. None / empty → "".
