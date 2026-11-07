# Profile-aware sponsorship scoring (score_v2.py, 2026-11-03)

`cand` = {"needs_sponsorship": bool, "citizen_or_pr": bool}. Label matching for "citizenship required" / "no sponsorship" is case-insensitive.

## sponsor_factor(label, cand=None)
Pure (tested). The sponsorship factor for a job's `sponsorship` label, for this candidate. A candidate who does not need sponsorship gets 1.0 whatever the label says (it does not matter to them). Otherwise: a label starting with "Blocked" → 0.0; "Posting offers sponsorship" 1.0, "Strong H-1B sponsor" 0.8, "Some H-1B history" 0.6, anything else 0.4.

## label_blocks(label, cand=None)
Pure (tested). Does a job's `sponsorship` label rule this candidate out? "Blocked: citizenship required" → only a candidate who is not a citizen / permanent resident; "Blocked: no sponsorship" → only a candidate who needs sponsorship; any other label starting with "Blocked" → yes (an unknown block stays a block); else no.
