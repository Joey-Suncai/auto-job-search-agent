A JSON array of 24 cases: {"name": str, "fn": "board_of"|"board_pick", "args": [...positional args; board_pick: options, source, url, default], "expect": <string or null>}.
About 8 board_of and 16 board_pick. Cover: sources linkedin / indeed_search / wellfound_search / dice_search / builtin /
handshake, URLs on linkedin.com, www.indeed.com, jobright.ai, a company icims.com page, null source + null url,
option spellings ("Linked In", "LinkedIn.com", "Indeed.com", "ZipRecruiter"), a list without the row's board (→ default),
a list without LinkedIn either (→ null), a Yes/No list (→ null), blank options, default not a board name.
