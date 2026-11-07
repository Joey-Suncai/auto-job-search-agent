Each case is a JSON object:
{
 "name": "short id",
 "job": {"id": "J1", "title": "...", "level": "Internship", "elig": "可投", "sponsorship": "Strong H-1B sponsor",
         "referral": "Cold", "posted": "2026-10-20", "added": "2026-10-25", "sources": "Simplify Summer 2027", "score": 55,
         "joey_pref": "up"},          // include only the fields the case needs; joey_pref optional
 "expect": {"v_level": "top", "s_chance": 0.5, "score": 85.0, "tier_orig": "A", "tier": "A", "score_v1": 55},  // only fields checked
 "spec_quote": "...",
 "ambiguous": false
}
