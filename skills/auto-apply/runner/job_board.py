#!/usr/bin/env python3
"""Which job board to name when a form asks "Please specify" after "How did you hear about us? = Job Board" (2026-11-03).

Joey 2026-11-03: 「如果这一行的来源正好是选项里的某个网站（比如来自 LinkedIn 或 Indeed），就选那个；否则一律选 LinkedIn」.
The default board lives in config/profile.json → answers.how_heard_board.default (JSA-077: facts in config, not code).
"""
import re

# board → words that name it in an option text, a store `source` value or a URL host
BOARDS = {
    'LinkedIn': r'linked\s*in',
    'Indeed': r'indeed',
    'Glassdoor': r'glassdoor',
    'ZipRecruiter': r'zip\s*recruiter',
    'Monster': r'monster',
    'CareerBuilder': r'career\s*builder',
    'Handshake': r'handshake|joinhandshake',
    'Wellfound': r'wellfound|angel\s*list|angel\.co',
    'Dice': r'\bdice\b|dice\.com|dice_search',
    'Built In': r'built\s*in|builtin',
    'Craigslist': r'craigslist',
    'Simplify': r'simplify',
}


def board_of(source, url):
    """Pure (tested). The board a store row came from: its `source` value first, then its URL host; None when neither
    names a known board (a company career site, a GitHub list, an aggregator such as jobright)."""
    for text in (str(source or ''), re.sub(r'^https?://', '', str(url or '')).split('/')[0]):
        for name, rx in BOARDS.items():
            if text and re.search(rx, text, re.I):
                return name
    return None


def board_pick(options, source=None, url=None, default='LinkedIn'):
    """Pure (tested). The option to choose: the one naming the row's own board (board_of) when the list has it, else the
    one naming `default` (a board name, or a list tried in order: LinkedIn, then Indeed — Joey 2026-11-03); None when the
    options name no known board at all (not a job-board list) or none of them is there.
    Option matching is case-insensitive on the board's words; the first matching option wins."""
    opts = [str(o) for o in (options or []) if str(o).strip()]
    if not any(re.search(rx, o, re.I) for o in opts for rx in BOARDS.values()):
        return None
    defaults = list(default) if isinstance(default, (list, tuple)) else [default]
    for name in [board_of(source, url)] + defaults:
        if not name or name not in BOARDS:
            continue
        hit = next((o for o in opts if re.search(BOARDS[name], o, re.I)), None)
        if hit:
            return hit
    return None
