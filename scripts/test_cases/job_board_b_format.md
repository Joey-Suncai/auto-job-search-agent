A JSON array of 24 cases: {"name": str, "fn": "board_of"|"board_pick", "args": [...positional args; board_pick: options, source, url, default], "expect": <string or null>}.
Only board_pick, 10 cases, all with `default` as a LIST such as ["LinkedIn", "Indeed"]: LinkedIn listed, LinkedIn missing but Indeed listed, neither listed, the row's own board listed (wins), list containing a non-board name, empty list.
handshake, URLs on linkedin.com, www.indeed.com, jobright.ai, a company icims.com page, null source + null url,
option spellings ("Linked In", "LinkedIn.com", "Indeed.com", "ZipRecruiter"), a list without the row's board (→ default),
a list without LinkedIn either (→ null), a Yes/No list (→ null), blank options, default not a board name.
