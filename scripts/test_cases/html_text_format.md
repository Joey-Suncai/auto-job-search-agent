A JSON array of 18 cases: {"name": str, "html": "<html mail>", "expect": "<code>" or null}.
Include mails whose <style> block mentions "code" (CSS selectors like ".x code { ... }", hex colours, "0.123456em" sizes)
before the real code sentence, uppercase <STYLE>, <script> blocks, codes inside <b>/<span>, codes split from the word by
tags, no code at all, a year after "code", a 5-digit and an 11-digit number (not codes), letters+digits codes.
